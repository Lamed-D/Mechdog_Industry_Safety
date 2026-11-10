"""Pure scheduling intents with injected durable run reservation, no ROS or network."""
from dataclasses import dataclass
from datetime import datetime, timezone
import math
from host.hub.store import identity


@dataclass(frozen=True)
class Ready:
    connected: bool
    telemetry_fresh: bool
    battery_ok: bool
    unlatched: bool
    position_trusted: bool
    path_safe: bool
    map_version: int

    def reason(self, version):
        for name in ('connected','telemetry_fresh','battery_ok','unlatched','position_trusted','path_safe'):
            if getattr(self,name) is not True:
                return name+'_required'
        if type(self.map_version) is not int or self.map_version!=version:
            return 'map_version_mismatch'
        return None


def schedule(value):
    if not isinstance(value,dict):
        raise ValueError('schedule required')
    kind = value.get('kind')
    if kind=='manual' and set(value)=={'kind'}:
        return dict(value)
    if (kind=='daily' and set(value)=={'kind','hour','minute','timezone'}
            and value['timezone']=='UTC' and type(value['hour']) is int and 0<=value['hour']<24
            and type(value['minute']) is int and 0<=value['minute']<60):
        return dict(value)
    if (kind=='interval' and set(value)=={'kind','seconds','anchor_utc'}
            and type(value['seconds']) is int and value['seconds']>0
            and isinstance(value['anchor_utc'],str) and value['anchor_utc'].endswith('Z')):
        anchor = datetime.fromisoformat(value['anchor_utc'][:-1]+'+00:00').timestamp()
        return dict(value,anchor=anchor)
    raise ValueError('unsupported schedule')


class Scheduler:
    def __init__(self, routines, version, reserve_run):
        if type(version) is not int or version<1 or not callable(reserve_run):
            raise ValueError('confirmed version and durable reservation required')
        self.version, self.reserve = version, reserve_run
        self.routines = {}
        for row in routines:
            key = identity(row['id'])
            if key in self.routines or row.get('robot_id') not in ('A','B') or type(row['enabled']) is not bool:
                raise ValueError('unique routine with assigned robot required')
            self.routines[key] = dict(id=key,route_id=identity(row['route_id']),robot=row['robot_id'],
                                      enabled=row['enabled'],schedule=schedule(row['schedule']))
        self.running = {}
        self.held = True  # No scheduled start after boot until an admitted human resume.
        self.seen = {}
        self.last_wall = None

    def _ready(self, ready, robot):
        state = ready.get(robot)
        return state.reason(self.version) if isinstance(state,Ready) else 'telemetry_required'

    def resume(self, ready, *, human_confirmed=False, internet_ok=False):
        if human_confirmed is not True or internet_ok is not True or any(self._ready(ready,r) for r in ('A','B')):
            return False
        self.held = False
        return True

    def _start(self, row, key, ready):
        robot = row['robot']
        reason = self._ready(ready,robot)
        if self.held or reason or robot in self.running:
            return dict(kind='rejected',robot=robot,reason=reason or 'scheduler_held_or_busy')
        try:
            if self.reserve(key) is not True:
                raise ValueError('run already reserved')
        except Exception:
            return dict(kind='rejected',robot=robot,reason='run_reservation_failed')
        self.running[robot] = dict(run_key=key,routine_id=row['id'],route_id=row['route_id'])
        return dict(kind='start_route',robot=robot,**self.running[robot])

    def tick(self, now_utc, ready, *, clock_trusted=False, internet_ok=False,
             incident=False, estop=False, manual=()):
        if any(type(v) is not bool for v in (clock_trusted,internet_ok,incident,estop)):
            raise ValueError('explicit safety booleans required')
        output = []
        reason = 'estop' if estop else 'incident' if incident else 'internet_lost' if not internet_ok else None
        if reason:
            self.held = True
            for robot in ('A','B'):
                output.append(dict(kind='stop',robot=robot,reason=reason))
            self.running.clear()
            return output
        trusted_time = (clock_trusted is True and not isinstance(now_utc,bool)
                        and isinstance(now_utc,(int,float)) and math.isfinite(now_utc))
        if trusted_time and self.last_wall is not None and now_utc<self.last_wall:
            self.held = True
            output.extend(dict(kind='stop',robot=r,reason='clock_reversed') for r in self.running)
            self.running.clear()
            return output
        for robot in list(self.running):
            fault = self._ready(ready,robot)
            if fault:
                self.held = True
                # Stop every routine on a readiness fault, then require human resume.
                output.extend(dict(kind='stop',robot=r,reason=fault) for r in self.running)
                self.running.clear()
                break
        for routine_id,request_id in manual:
            identity(request_id)
            row = self.routines.get(routine_id)
            if row is None or not row['enabled']:
                output.append(dict(kind='rejected',reason='routine_disabled_or_unknown'))
            else:
                output.append(self._start(row,f'{routine_id}:{self.version}:manual:{request_id}',ready))
        if not trusted_time:
            return output
        self.last_wall = now_utc
        now = datetime.fromtimestamp(now_utc,timezone.utc)
        for key,row in self.routines.items():
            config = row['schedule']
            if not row['enabled'] or config['kind']=='manual':
                continue
            if config['kind']=='daily':
                if (now.hour,now.minute)!=(config['hour'],config['minute']):
                    continue  # No missed-time catch-up.
                slot = now.date().isoformat()
            else:
                elapsed = now_utc-config['anchor']
                if elapsed<0:
                    continue
                slot = str(int(elapsed//config['seconds']))
            if self.seen.get(key)==slot:
                continue
            self.seen[key] = slot  # Blocked slots are not silently started later.
            output.append(self._start(row,f'{key}:{self.version}:{slot}',ready))
        return output

    def completed(self, robot):
        run = self.running.pop(robot,None)
        return None if run is None else dict(kind='routine_done',robot=robot,**run)
