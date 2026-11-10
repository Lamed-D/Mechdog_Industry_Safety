"""Validate an immutable confirmed snapshot before replacing the local active copy."""
import hashlib
import json
import math
from pathlib import PurePosixPath
from host.map_review import Grid, approve_edit
from host.hub.store import CONFIG_LIMIT, digest_config, encode, identity

REQUIRED = {'start_wait','manager','server','inspection'}


def grid_file(meta, fetch):
    path = meta['object_path']
    if (not isinstance(path,str) or not path or '\\' in path or '\x00' in path
            or PurePosixPath(path).is_absolute() or any(p in ('','.','..') for p in path.split('/'))):
        raise ValueError('invalid private object path')
    raw = fetch(path,CONFIG_LIMIT)
    if not isinstance(raw,bytes) or len(raw)>CONFIG_LIMIT or hashlib.sha256(raw).hexdigest()!=meta['sha256']:
        raise ValueError('map file digest mismatch')
    def pairs(items):
        result = {}
        for key,value in items:
            if key in result:
                raise ValueError('duplicate map key')
            result[key] = value
        return result
    data = json.loads(raw,object_pairs_hook=pairs)
    if not isinstance(data,dict) or set(data)!={'width','height','resolution','origin','cells','frame'}:
        raise ValueError('canonical grid JSON required')
    grid = Grid(**data)
    geometry = dict(width=grid.width,height=grid.height,resolution=grid.resolution,
                    origin=list(grid.origin),frame=grid.frame)
    if meta['geometry']!=geometry:
        raise ValueError('map geometry mismatch')
    return grid


def point(value):
    if (not isinstance(value,(list,tuple)) or len(value)!=2 or
            any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in value)):
        raise ValueError('finite point required')
    return tuple(value)


def cross(a,b,p):
    return (b[0]-a[0])*(p[1]-a[1])-(b[1]-a[1])*(p[0]-a[0])


def on_segment(a,b,p):
    return cross(a,b,p)==0 and min(a[0],b[0])<=p[0]<=max(a[0],b[0]) and min(a[1],b[1])<=p[1]<=max(a[1],b[1])


def intersects(a,b,c,d):
    return (on_segment(a,b,c) or on_segment(a,b,d) or on_segment(c,d,a) or on_segment(c,d,b)
            or (cross(a,b,c)*cross(a,b,d)<0 and cross(c,d,a)*cross(c,d,b)<0))


def inside(p, polygon):
    result = False
    for a,b in zip(polygon,polygon[1:]+polygon[:1]):
        if on_segment(a,b,p):
            return True
        if (a[1]>p[1])!=(b[1]>p[1]) and p[0] < (b[0]-a[0])*(p[1]-a[1])/(b[1]-a[1])+a[0]:
            result = not result
    return result


def polygon(value):
    if not isinstance(value,list) or not 3<=len(value)<=256:
        raise ValueError('bounded polygon required')
    poly = [point(p) for p in value]
    if len(set(poly))!=len(poly):
        raise ValueError('duplicate polygon vertex')
    edges = list(zip(poly,poly[1:]+poly[:1]))
    if sum(a[0]*b[1]-b[0]*a[1] for a,b in edges)==0:
        raise ValueError('degenerate polygon')
    for i,(a,b) in enumerate(edges):
        for j,(c,d) in enumerate(edges):
            if j>i+1 and (i,j)!=(0,len(edges)-1) and intersects(a,b,c,d):
                raise ValueError('self intersecting polygon')
    return poly


def cell(grid,p):
    dx,dy = p[0]-grid.origin[0],p[1]-grid.origin[1]
    yaw = grid.origin[2]
    x = (math.cos(yaw)*dx+math.sin(yaw)*dy)/grid.resolution
    y = (-math.sin(yaw)*dx+math.cos(yaw)*dy)/grid.resolution
    if not 0<=x<grid.width or not 0<=y<grid.height:
        raise ValueError('point outside map')
    return math.floor(y)*grid.width+math.floor(x)


def validate(snapshot, fetch, authorize_confirmation):
    # Detach all nested caller objects before checking and storing.
    snapshot = json.loads(encode(snapshot,CONFIG_LIMIT))
    if snapshot['state']!='confirmed' or type(snapshot['version']) is not int or snapshot['version']<1:
        raise ValueError('confirmed version required')
    hub, meta = identity(snapshot['hub_id']), snapshot['map']
    map_id = identity(meta['id'])
    if (meta['hub_id']!=hub or meta['state']!='confirmed' or meta['version']!=snapshot['version']
            or authorize_confirmation(meta['confirmed_by']) is not True or not meta['confirmed_at']):
        raise ValueError('trusted human confirmation required')
    candidate = grid_file(meta,fetch)
    base_meta = snapshot['base_map']
    if base_meta['hub_id']!=hub or base_meta['sha256']!=meta['base_sha256']:
        raise ValueError('base map mismatch')
    base = grid_file(base_meta,fetch)
    approve_edit(base,candidate,expected_base_digest=base.digest(),
                 expected_proposal_digest=candidate.digest(),approved_clearings=meta['approved_clearings'])
    forbidden = []
    all_ids = set()
    def rows(table):
        result = snapshot[table]
        if not isinstance(result,list) or len(result)>1000:
            raise ValueError('bounded configuration rows required')
        for row in result:
            key = identity(row['id'])
            if key in all_ids or row['hub_id']!=hub:
                raise ValueError('duplicate or foreign configuration row')
            all_ids.add(key)
            if table not in ('routines',) and row['map_id']!=map_id:
                raise ValueError('map version mismatch')
        return result
    for zone in rows('zones'):
        poly = polygon(zone['geometry']['polygon'])
        for p in poly:
            cell(candidate,p)
        if zone['kind']=='forbidden':
            forbidden.append(poly)
        elif zone['kind'] not in ('patrol','slow'):
            raise ValueError('unknown zone kind')
    waypoints, kinds = {},set()
    for waypoint in rows('waypoints'):
        pose = waypoint['pose']
        p = point([pose['x'],pose['y']])
        yaw = pose['yaw']
        if isinstance(yaw,bool) or not isinstance(yaw,(int,float)) or not math.isfinite(yaw):
            raise ValueError('finite heading required')
        if candidate.cells[cell(candidate,p)]!=0 or any(inside(p,poly) for poly in forbidden):
            raise ValueError('waypoint not traversable')
        if waypoint['kind'] not in REQUIRED:
            raise ValueError('unknown waypoint kind')
        kinds.add(waypoint['kind'])
        waypoints[waypoint['id']] = p
    if not REQUIRED<=kinds:
        raise ValueError('four waypoint kinds required')
    route_ids = set()
    for route in rows('routes'):
        points = route['points']
        if (not isinstance(points,list) or not 1<=len(points)<=1000
                or any(key not in waypoints for key in points)):
            raise ValueError('invalid route waypoints')
        for a,b in zip(points,points[1:]):
            start,end = waypoints[a],waypoints[b]
            if any(intersects(start,end,c,d) for poly in forbidden for c,d in zip(poly,poly[1:]+poly[:1])):
                raise ValueError('route crosses forbidden zone')
        route_ids.add(route['id'])
    for routine in rows('routines'):
        if routine['route_id'] not in route_ids or type(routine['enabled']) is not bool:
            raise ValueError('invalid routine route')
    snapshot['validated_grid'] = dict(width=candidate.width,height=candidate.height,
        resolution=candidate.resolution,origin=list(candidate.origin),frame=candidate.frame,
        cells=list(candidate.cells))
    # Executability (footprint, inflation, obstacle-free path, schedule) is checked by Navigator/scheduler.
    return snapshot


class ConfigSync:
    def __init__(self, store, fetch, authorize_confirmation, report):
        self.store, self.fetch = store, fetch
        self.authorize, self.report = authorize_confirmation, report
        self.report_failures = 0

    def apply(self, snapshot):
        stage = 'configuration_validation_failed'
        try:
            value = validate(snapshot,self.fetch,self.authorize)
            stage = 'configuration_activation_failed'
            if not self.store.activate_config(value['version'],value,digest_config(value)):
                raise ValueError('activation failed')
            result = {'ok':True,'reason':'activated','version':value['version']}
        except Exception:
            result = {'ok':False,'reason':stage}
        try:
            self.report(result.copy())
        except Exception:
            self.report_failures += 1
        return result
