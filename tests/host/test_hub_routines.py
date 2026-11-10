from dataclasses import replace
from datetime import datetime, timezone
import unittest
import uuid
from pathlib import Path
import tempfile
from host.hub.store import Store
from host.hub.routines import Ready, Scheduler, schedule


class RoutineTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026,1,1,12,tzinfo=timezone.utc).timestamp()
        self.row = dict(id=str(uuid.uuid4()),route_id=str(uuid.uuid4()),robot_id='A',enabled=True,
                        schedule=dict(kind='daily',hour=12,minute=0,timezone='UTC'))
        self.reserved = set()
        self.ready = dict.fromkeys(('A','B'),Ready(True,True,True,True,True,True,1))
        self.scheduler = self.build()

    def reserve(self, key):
        if key in self.reserved:
            return False
        self.reserved.add(key)
        return True

    def build(self):
        return Scheduler([self.row],1,self.reserve)

    def arm(self):
        self.assertTrue(self.scheduler.resume(self.ready,human_confirmed=True,internet_ok=True))

    def tick(self, **changes):
        args = dict(clock_trusted=True,internet_ok=True)
        args.update(changes)
        return self.scheduler.tick(self.now,self.ready,**args)

    def test_boot_and_untrusted_clock_do_not_schedule(self):
        self.assertNotIn('start_route',[x['kind'] for x in self.tick()])
        self.scheduler = self.build()
        self.arm()
        self.assertEqual(self.tick(clock_trusted=False),[])
        self.assertEqual(self.tick()[0]['kind'],'start_route')

    def test_daily_once_and_restart_uses_durable_reservation(self):
        self.arm()
        self.assertEqual(self.tick()[0]['kind'],'start_route')
        self.assertEqual(self.tick(),[])
        self.scheduler.completed('A')
        self.scheduler = self.build()
        self.arm()
        self.assertEqual(self.tick()[0]['reason'],'run_reservation_failed')

    def test_all_readiness_gates_block_start(self):
        for field in ('connected','telemetry_fresh','battery_ok','unlatched','position_trusted','path_safe','map_version'):
            self.scheduler = self.build()
            self.arm()
            self.ready['A'] = replace(self.ready['A'],**{field:2 if field=='map_version' else False})
            self.assertNotIn('start_route',[x['kind'] for x in self.tick()])
            self.ready['A'] = Ready(True,True,True,True,True,True,1)

    def test_incident_estop_and_disconnect_hold_until_human(self):
        for flag in ('incident','estop','internet_ok'):
            self.scheduler = self.build()
            self.arm()
            output = self.tick(**{flag:False if flag=='internet_ok' else True})
            self.assertEqual([x['kind'] for x in output],['stop','stop'])
            self.assertTrue(self.scheduler.held)
            self.assertNotIn('start_route',[x['kind'] for x in self.tick()])

    def test_manual_request_id_is_reserved_and_does_not_need_schedule_clock(self):
        self.row['schedule'] = {'kind':'manual'}
        self.scheduler = self.build()
        self.arm()
        request = (self.row['id'],str(uuid.uuid4()))
        self.assertEqual(self.tick(clock_trusted=False,manual=[request])[0]['kind'],'start_route')
        self.assertIsNotNone(self.scheduler.completed('A'))
        self.assertEqual(self.tick(manual=[request])[0]['reason'],'run_reservation_failed')

    def test_interval_and_clock_reversal_stops(self):
        self.row['schedule'] = dict(kind='interval',seconds=60,anchor_utc='2026-01-01T12:00:00Z')
        self.scheduler = self.build()
        self.arm()
        self.assertEqual(self.tick()[0]['kind'],'start_route')
        self.now -= 1
        self.assertEqual(self.tick()[0]['reason'],'clock_reversed')
        self.assertTrue(self.scheduler.held)

    def test_invalid_schedules_and_reservation_failure(self):
        for value in ({'kind':'daily','hour':24,'minute':0,'timezone':'UTC'},
                      {'kind':'interval','seconds':0,'anchor_utc':'2026-01-01T00:00:00Z'},
                      {'kind':'manual','extra':1}):
            with self.assertRaises(ValueError):
                schedule(value)
        self.arm()
        self.scheduler.reserve = lambda key:(_ for _ in ()).throw(OSError('synthetic'))
        self.assertEqual(self.tick()[0]['reason'],'run_reservation_failed')

    def test_sqlite_run_reservation_survives_restart(self):
        root = Path(__file__).resolve().parents[2]/'build'
        root.mkdir(exist_ok=True)
        hub = '00000000-0000-4000-8000-000000000001'
        with tempfile.TemporaryDirectory(dir=root) as directory:
            path = str(Path(directory)/'runs.db')
            store = Store(path,hub,hub)
            self.assertTrue(store.reserve_run('synthetic:run:1'))
            store.close()
            store = Store(path,hub,hub)
            try:
                self.assertFalse(store.reserve_run('synthetic:run:1'))
                self.assertTrue(store.reserve_run('synthetic:run:2'))
            finally:
                store.close()
