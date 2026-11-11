"""Synthetic cloud/hub integration. No sockets, accounts, robot devices or models."""
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import threading
import uuid
from dashboard.web.run import build_sim
from host.hub.commands import Processor
from host.hub.config_sync import ConfigSync, REQUIRED
from host.hub.connectivity import Connectivity, WeakLimits, Link, dispatch_returns
from host.hub.routines import Scheduler, Ready
from host.hub.store import Store
from host.hub.sync import Sync
from tools.mock.fake_supabase import FakeSupabase


def key(name):
    return str(uuid.uuid5(uuid.NAMESPACE_URL,'urn:synthetic:mechdog:'+name))


def run_demo(finder='A', navigator_available=True):
    if finder not in ('A','B') or type(navigator_available) is not bool:
        raise ValueError('synthetic demo option required')
    now = [0.0]
    wall = lambda:1767225600+now[0]
    stamp = lambda value:datetime.fromtimestamp(value,timezone.utc).isoformat().replace('+00:00','Z')
    hub, device = key('hub'), key('dashboard')
    store = Store(':memory:',hub,hub)
    core, links = build_sim(clock=lambda:now[0],wall=wall)
    cloud = FakeSupabase()
    sync = Sync(store,cloud,clock=lambda:now[0])
    processor = Processor(core,store,lambda d:('estop','reset','operator') if d==device else (),
        threading.RLock(),wall=wall,clock=lambda:now[0],clock_trusted=lambda:True)
    timeline, sequence = [], [0]

    def record(event, **detail):
        timeline.append(dict(source='synthetic',hardware=False,time_s=now[0],event=event,detail=detail))
        store.enqueue('events',dict(id=key('event'+str(len(timeline))),hub_id=hub,device_id=hub,
            created_at=stamp(wall()),kind=event,detail=dict(source='synthetic',**detail)))

    def exchange():
        now[0] += 1.1
        for link in links.values():
            link.step()
        core.update()
        outcomes = processor.process(sync.tick())
        for link in links.values():
            link.step()
        core.update()
        processor.reconcile_resets()
        # Intent consumption only: this demo has no robot movement executor.
        for command in core.drain_commands():
            record('scenario_intent',**asdict(command))
        return outcomes

    def send(kind, payload, robot=None):
        sequence[0] += 1
        row = dict(v=1,id=key('command'+str(sequence[0])),hub_id=hub,device_id=device,
            robot_id=robot,kind=kind,payload=payload,created_at=stamp(wall()),expires_at=stamp(wall()+10))
        cloud.pending.append(row)
        result = exchange()
        record('cloud_command',kind=kind,outcomes=result)
        return row['id']

    def drain():
        for _ in range(200):
            if store.peek() is None:
                return
            exchange()
        raise AssertionError('synthetic outbox did not drain')

    try:
        geometry = dict(width=4,height=4,resolution=1,origin=[0,0,0],frame='map')
        raw = json.dumps(dict(geometry,cells=[0]*16)).encode()
        digest = hashlib.sha256(raw).hexdigest()
        base = dict(id=key('base'),hub_id=hub,geometry=geometry,object_path='synthetic/base.json',sha256=digest)
        meta = dict(base,id=key('map'),version=2,state='confirmed',base_sha256=digest,
            approved_clearings=[],confirmed_by=device,confirmed_at=stamp(wall()))
        points = [dict(id=key(kind),hub_id=hub,map_id=meta['id'],kind=kind,
            pose=dict(x=index+.5,y=.5,yaw=0)) for index,kind in enumerate(sorted(REQUIRED))]
        route = dict(id=key('route'),hub_id=hub,map_id=meta['id'],points=[p['id'] for p in points])
        routine = dict(id=key('routine'),hub_id=hub,robot_id=finder,route_id=route['id'],enabled=True,schedule={'kind':'manual'})
        snapshot = dict(hub_id=hub,state='confirmed',version=2,map=meta,base_map=base,
            zones=[],waypoints=points,routes=[route],routines=[routine])
        config = ConfigSync(store,lambda path,limit:raw,lambda d:d==device,lambda result:record('config',**result))
        if not config.apply(snapshot)['ok']:
            raise AssertionError('synthetic config rejected')
        exchange()
        for robot in ('A','B'):
            send('reset',dict(confirmed=True,reset_context=processor.reset_contexts()[robot]),robot)
        ready = {robot:Ready(True,True,True,True,True,True,2) for robot in ('A','B')}
        scheduler = Scheduler([routine],2,store.reserve_run)
        scheduler.resume(ready,human_confirmed=True,internet_ok=sync.internet_ok())
        started = scheduler.tick(wall(),ready,clock_trusted=True,internet_ok=True,
            manual=[(routine['id'],key('manual-start'))])
        record('routine_start',intents=started)
        send('operator',{'event':'start_patrol'})
        # The evidence is deliberately injected; this does not test a vision model.
        core.detection(dict(robot=finder,status='needs_check',source='synthetic',confidence=.7))
        incident_stops = scheduler.tick(wall(),ready,clock_trusted=True,internet_ok=True,incident=True)
        alert_id = key('alert')
        alert = dict(id=alert_id,hub_id=hub,device_id=hub,robot_id=finder,
            created_at=stamp(wall()),updated_at=stamp(wall()),state='open',evidence={'source':'synthetic','needs_check':True})
        store.enqueue('alerts',alert)
        record('incident',intents=incident_stops,phase=core.scenario.phase)
        drain()
        ack_id = send('operator',{'event':'operator_ack'})
        store.enqueue('alerts',dict(alert,state='acked',updated_at=stamp(wall())))
        drain()
        # Weak thresholds below are test fixtures, never field defaults.
        policy = Connectivity(WeakLimits(.3,.2))
        network = {robot:Link(True,0,0,False,True,True) for robot in ('A','B')}
        policy.tick(now[0],sync.last_success,network,human_resume=True)
        cloud.offline = True
        now[0] += 10.1
        sync.tick()
        returns = policy.tick(now[0],sync.last_success,network)
        # Pause the incident/scenario before admitting any synthetic return intent.
        for robot in ('A','B'):
            core.command_blocked(robot,'patrol','internet_lost')
        scheduler.tick(wall(),ready,clock_trusted=True,internet_ok=False)
        class SyntheticNavigator:
            def return_to_server(self, robot):
                record('synthetic_return_request',robot=robot)
                return True
        returns = dispatch_returns(policy,returns,SyntheticNavigator() if navigator_available else None)
        record('offline_return',intents=[asdict(intent) for intent in returns])
        policy.tick(now[0],sync.last_success,network,arrived=('A','B'))
        cloud.offline = False
        exchange()
        after = policy.tick(now[0],sync.last_success,network)
        record('reconnected',intents=[asdict(intent) for intent in after])
        drain()
        return dict(source='synthetic',hardware=False,timeline=timeline,
            active_version=store.active_config()['version'],routine_started=started[0]['kind']=='start_route',
            alert_uploaded=('alerts',alert_id) in cloud.rows,
            alert_state=cloud.rows.get(('alerts',alert_id),{}).get('state'),
            ack_status=cloud.rows.get(('commands',ack_id),{}).get('status'),
            command_count=len([row for (table,_),row in cloud.rows.items() if table=='commands']),
            phase=core.scenario.phase,states=dict(policy.states),paused=policy.paused,scheduler_held=scheduler.held,
            automatic_resume=any(intent.kind=='resume_patrol' for intent in after))
    finally:
        core.log.close()
        store.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--finder',choices=('A','B'),default='A')
    parser.add_argument('--no-navigator',action='store_true')
    args = parser.parse_args()
    result = run_demo(args.finder,not args.no_navigator)
    for row in result.pop('timeline'):
        print(json.dumps(row,ensure_ascii=False))
    print(json.dumps(dict(event='summary',**result),ensure_ascii=False))


if __name__ == '__main__':
    main()
