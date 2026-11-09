from pathlib import Path
import tempfile
import unittest
import uuid
from host.hub.store import Store, digest_config
from host.command_envelope import Command

HUB = '00000000-0000-4000-8000-000000000001'
OTHER = '00000000-0000-4000-8000-000000000002'


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.store = Store(':memory:',HUB,HUB,capacity=2)
        self.addCleanup(self.store.close)

    def row(self, **updates):
        row = dict(id=str(uuid.uuid4()),hub_id=HUB,device_id=HUB,robot_id='A',
                   created_at='2026-01-01T00:00:00Z',detail={'kind':'synthetic'})
        row.update(updates)
        return row

    def test_order_idempotency_copy_capacity_and_head_only_ack(self):
        first, second = self.row(), self.row()
        event = str(uuid.uuid4())
        self.assertTrue(self.store.enqueue('events',first,event_id=event))
        self.assertTrue(self.store.enqueue('events',first,event_id=event))
        self.assertTrue(self.store.enqueue('events',second))
        first['detail']['kind'] = 'changed'
        self.assertFalse(self.store.enqueue('events',first,event_id=event))
        self.assertFalse(self.store.enqueue('events',self.row()))
        head = self.store.peek()
        self.assertEqual(head.row['detail']['kind'],'synthetic')
        self.assertFalse(self.store.acknowledge(head.seq+1,head.event_id))
        self.assertTrue(self.store.acknowledge(head.seq,head.event_id))
        self.assertEqual(self.store.peek().row,second)

    def test_restart_keeps_queue_cache_and_existing_command_journal(self):
        root = Path(__file__).resolve().parents[2] / 'build'
        root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as directory:
            path = Path(directory)/'hub.db'
            store = Store(path,HUB,HUB)
            value = {'state':'confirmed','hub_id':HUB,'map_id':'synthetic'}
            self.assertTrue(store.activate_config(1,value,digest_config(value)))
            row = self.row(summary={'latched':True})
            self.assertTrue(store.save_status('A',row))
            command = Command(OTHER,HUB,OTHER,'A','reset',0,10,())
            self.assertTrue(store.journal.claim(command))
            store.close()
            restored = Store(path,HUB,HUB)
            try:
                self.assertEqual(restored.status('A'),row)
                self.assertEqual(restored.active_config()['value'],value)
                self.assertEqual(restored.peek().table,'robot_status')
                self.assertFalse(restored.journal.claim(command))
                with self.assertRaises(ValueError):
                    Store(path,OTHER,OTHER)
            finally:
                restored.close()

    def test_config_failure_or_old_version_does_not_replace_active_copy(self):
        value = {'state':'confirmed','hub_id':HUB,'points':[1,2]}
        self.assertTrue(self.store.activate_config(2,value,digest_config(value)))
        active = self.store.active_config()
        active['value']['points'].append(3)
        for version, changed, digest in ((1,value,digest_config(value)), (3,value,'wrong'),
                (2,{**value,'points':[]},digest_config({**value,'points':[]})),
                (3,{**value,'state':'draft'},digest_config({**value,'state':'draft'}))):
            self.assertFalse(self.store.activate_config(version,changed,digest))
        self.assertEqual(self.store.active_config()['value'],value)

    def test_bad_metadata_wrong_hub_or_write_failure_is_counted(self):
        for row in (self.row(detail=b'not metadata'), self.row(hub_id=OTHER), self.row(detail=float('nan'))):
            self.assertFalse(self.store.enqueue('events',row))
        self.assertFalse(self.store.enqueue('devices',self.row()))
        self.assertFalse(self.store.enqueue('commands',self.row()))
        self.store._db.execute('PRAGMA query_only=ON')
        self.assertFalse(self.store.enqueue('events',self.row()))
        self.assertGreaterEqual(self.store.failures,6)
        self.assertIsNone(self.store.peek())

    def test_status_and_queue_commit_together(self):
        initial = self.row(summary={'latched':True})
        self.assertTrue(self.store.save_status('A',initial))
        self.assertTrue(self.store.enqueue('events',self.row()))
        self.assertFalse(self.store.save_status('A',self.row(summary={'latched':False})))
        self.assertEqual(self.store.status('A'),initial)

    def test_command_result_cannot_overwrite_original_envelope(self):
        row = dict(id=OTHER,hub_id=HUB,status='done',result={'ok':True},updated_at='2026-01-01T00:00:00Z')
        self.assertTrue(self.store.enqueue('commands',row,operation='command_result'))
        self.assertFalse(self.store.enqueue('commands',{**row,'payload':{}},operation='command_result'))
