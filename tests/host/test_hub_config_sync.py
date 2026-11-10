import copy
import hashlib
import json
import unittest
import uuid
from host.hub.config_sync import ConfigSync, validate
from host.hub.store import Store

HUB = '00000000-0000-4000-8000-000000000001'


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.store = Store(':memory:',HUB,HUB)
        self.addCleanup(self.store.close)
        self.grid = dict(width=8,height=8,resolution=1,origin=[0,0,0],frame='map',cells=[0]*64)
        self.files = {}
        self.reports = []
        self.meta = dict(id=str(uuid.uuid4()),hub_id=HUB,state='confirmed',version=1,
                         object_path='synthetic/grid.json',approved_clearings=[],confirmed_by=HUB,
                         confirmed_at='2026-01-01T00:00:00Z')
        self.write_grid(self.grid)
        self.meta['base_sha256'] = self.meta['sha256']
        points = [dict(id=str(uuid.uuid4()),hub_id=HUB,map_id=self.meta['id'],kind=kind,
                       pose=dict(x=i+1.5,y=1.5,yaw=0))
                  for i,kind in enumerate(('start_wait','manager','server','inspection'))]
        route = dict(id=str(uuid.uuid4()),hub_id=HUB,map_id=self.meta['id'],points=[p['id'] for p in points])
        self.snapshot = dict(state='confirmed',hub_id=HUB,version=1,map=self.meta,
                             base_map=copy.deepcopy(self.meta),zones=[],waypoints=points,routes=[route],
                             routines=[dict(id=str(uuid.uuid4()),hub_id=HUB,route_id=route['id'],enabled=True,schedule={})])
        self.sync = ConfigSync(self.store,self.fetch,lambda who:who==HUB,self.reports.append)

    def write_grid(self, grid):
        raw = json.dumps(grid).encode()
        self.files[self.meta['object_path']] = raw
        self.meta['sha256'] = hashlib.sha256(raw).hexdigest()
        self.meta['geometry'] = {k:v for k,v in grid.items() if k!='cells'}

    def fetch(self, path, limit):
        self.assertEqual(limit,4*1024*1024)
        return self.files[path]

    def zone(self, poly):
        return dict(id=str(uuid.uuid4()),hub_id=HUB,map_id=self.meta['id'],kind='forbidden',geometry={'polygon':poly})

    def test_activate_copy_and_failure_keeps_old_version(self):
        self.assertTrue(self.sync.apply(self.snapshot)['ok'])
        old = self.store.active_config()
        self.snapshot['waypoints'][0]['pose']['x'] = -1
        self.assertFalse(self.sync.apply(self.snapshot)['ok'])
        self.assertEqual(self.store.active_config(),old)
        self.assertEqual(self.reports[-1]['reason'],'configuration_validation_failed')
        self.assertEqual(old['value']['validated_grid']['cells'],[0]*64)

    def test_file_hash_geometry_path_and_human_checks(self):
        for mutate in (lambda s:s['map'].update(sha256='0'*64),
                       lambda s:s['map']['geometry'].update(width=9),
                       lambda s:s['map'].update(object_path='../escape'),
                       lambda s:s['map'].update(confirmed_by='unregistered'),
                       lambda s:s['map'].update(state='draft')):
            value = copy.deepcopy(self.snapshot)
            mutate(value)
            self.assertFalse(self.sync.apply(value)['ok'])
        self.assertIsNone(self.store.active_config())

    def test_waypoint_required_kinds_obstacle_unknown_and_boundary(self):
        for kind in ('missing','outside','unknown','obstacle'):
            value = copy.deepcopy(self.snapshot)
            if kind=='missing':
                value['waypoints'].pop()
            elif kind=='outside':
                value['waypoints'][0]['pose']['x'] = 8
            else:
                self.grid['cells'][9] = -1 if kind=='unknown' else 50
                self.write_grid(self.grid)
                value['map'] = copy.deepcopy(self.meta)
                value['map']['base_sha256'] = self.meta['sha256']
                value['base_map'] = copy.deepcopy(value['map'])
            self.assertFalse(self.sync.apply(value)['ok'])

    def test_forbidden_boundary_crossing_and_self_intersection(self):
        for poly in ([[1.5,1],[2,1],[2,2],[1.5,2]],
                     [[2.75,1],[3,1],[3,2],[2.75,2]],
                     [[1,1],[4,4],[1,4],[4,1]]):
            value = copy.deepcopy(self.snapshot)
            value['zones'] = [self.zone(poly)]
            self.assertFalse(self.sync.apply(value)['ok'])

    def test_unknown_to_free_rejected_even_with_approval(self):
        base = copy.deepcopy(self.grid)
        base['cells'][0] = -1
        raw = json.dumps(base).encode()
        self.files['synthetic/base.json'] = raw
        self.snapshot['base_map'].update(object_path='synthetic/base.json',sha256=hashlib.sha256(raw).hexdigest())
        self.meta.update(base_sha256=self.snapshot['base_map']['sha256'],approved_clearings=[0])
        self.assertFalse(self.sync.apply(self.snapshot)['ok'])

    def test_foreign_route_and_reporting_failure_preserve_activation(self):
        value = copy.deepcopy(self.snapshot)
        value['routes'][0]['hub_id'] = str(uuid.uuid4())
        self.assertFalse(self.sync.apply(value)['ok'])
        self.sync.report = lambda result:(_ for _ in ()).throw(OSError('synthetic'))
        self.assertTrue(self.sync.apply(self.snapshot)['ok'])
        self.assertEqual(self.sync.report_failures,1)
        self.assertIsNotNone(self.store.active_config())

    def test_validation_returns_detached_snapshot(self):
        zone = self.zone([[1,3],[2,3],[2,4],[1,4]])
        zone['kind'] = 'slow'
        self.snapshot['zones'] = [zone]
        result = validate(self.snapshot,self.fetch,lambda who:True)
        self.snapshot['waypoints'][0]['pose']['x'] = 99
        self.assertEqual(result['waypoints'][0]['pose']['x'],1.5)
