from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import threading
import unittest
import uuid
from dashboard.web.run import build_sim
from host.hub.commands import Processor
from host.hub.map_confirmation import MapConfirmer
from host.hub.store import Store

HUB = '00000000-0000-4000-8000-000000000001'
DEVICE = '00000000-0000-4000-8000-000000000002'


class MapConfirmationTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026,1,1,tzinfo=timezone.utc).timestamp()
        self.trusted, self.permissions = True, ('estop','map_confirm')
        self.store = Store(':memory:',HUB,HUB)
        self.addCleanup(self.store.close)
        core, self.links = build_sim(clock=lambda:0,wall=lambda:self.now)
        self.addCleanup(core.log.close)
        self.lock = threading.RLock()
        self.files, self.rows, self.writes = {}, {}, []
        for version,cells in ((1,[100,-1]),(2,[0,-1])):
            key = str(uuid.uuid4())
            geometry = dict(width=2,height=1,resolution=1,origin=[0,0,0],frame='map')
            raw = json.dumps(dict(geometry,cells=cells)).encode()
            path = f'synthetic/{version}.json'
            self.files[path] = raw
            self.rows[key] = dict(id=key,hub_id=HUB,device_id=HUB,robot_id=None,
                created_at='2026-01-01T00:00:00Z',version=version,state='draft',geometry=geometry,
                object_path=path,sha256=hashlib.sha256(raw).hexdigest())
        base, proposal = self.rows.values()
        self.payload = dict(base_map_id=base['id'],proposal_map_id=proposal['id'],
            base_sha256=base['sha256'],proposal_sha256=proposal['sha256'],approved_clearings=[0])
        self.authorize = lambda device:self.permissions if device==DEVICE else ()
        def metadata(key):
            self.assertFalse(self.lock._is_owned(), 'map IO must not hold control lock')
            return self.rows[key]
        self.confirmer = MapConfirmer(self.store,metadata,lambda path,limit:self.files[path],
            wall=lambda:self.now,clock_trusted=lambda:self.trusted,authorize=self.authorize)
        enqueue = self.store.enqueue
        def capture(table,row,**kwargs):
            if table=='maps':
                self.writes.append(deepcopy(row))
            return enqueue(table,row,**kwargs)
        self.store.enqueue = capture
        self.processor = Processor(core,self.store,self.authorize,self.lock,wall=lambda:self.now,
            clock=lambda:0,clock_trusted=lambda:self.trusted,map_confirmer=self.confirmer)

    def row(self, **updates):
        row = dict(v=1,id=str(uuid.uuid4()),hub_id=HUB,device_id=DEVICE,robot_id=None,
            kind='map_confirm',created_at='2026-01-01T00:00:00Z',expires_at='2026-01-01T00:00:10Z',
            payload=deepcopy(self.payload))
        row.update(updates)
        return row

    def test_confirmation_is_queued_once_without_activation_or_motion(self):
        row = self.row()
        self.assertEqual(self.processor.process([row,row]),['done','done'])
        self.assertEqual(len(self.writes),1)
        self.assertEqual(self.writes[0]['confirmed_by'],DEVICE)
        self.assertEqual(self.writes[0]['device_id'],HUB)
        self.assertEqual(self.writes[0]['state'],'confirmed')
        self.assertIsNone(self.store.active_config())
        self.assertTrue(all(not link.sent for link in self.links.values()))
        self.assertEqual(self.rows[self.payload['proposal_map_id']]['state'],'draft')

    def test_changed_hash_and_incomplete_approvals_are_rejected(self):
        for changes in ({'approved_clearings':[]},{'approved_clearings':[True]},
                        {'approved_clearings':[0,0]},{'approved_clearings':list(range(129))},
                        {'base_sha256':'0'*64},{'proposal_map_id':self.payload['base_map_id']}):
            self.assertEqual(self.processor.process([self.row(payload=dict(self.payload,**changes))]),['rejected'])
        self.rows[self.payload['proposal_map_id']]['geometry']['origin'] = [1,0,0]
        self.assertEqual(self.processor.process([self.row()]),['rejected'])
        self.assertEqual(self.writes,[])

    def test_expiry_and_permission_are_rechecked_after_file_download(self):
        fetch = self.confirmer.fetch
        def slow(path,limit):
            self.now += 6
            return fetch(path,limit)
        self.confirmer.fetch = slow
        self.assertEqual(self.processor.process([self.row()]),['rejected'])
        self.now -= 12
        def revoked(path,limit):
            self.permissions = ()
            return fetch(path,limit)
        self.confirmer.fetch = revoked
        self.assertEqual(self.processor.process([self.row()]),['rejected'])
        self.assertEqual(self.writes,[])

    def test_stop_wins_and_missing_handler_fails_closed(self):
        self.assertEqual(self.processor.process([self.row(),self.row(kind='estop',payload={})]),['done','rejected'])
        self.assertEqual(self.writes,[])
        self.processor.map_confirmer = None
        self.assertEqual(self.processor.process([self.row()]),['rejected'])
        self.assertTrue(all('ESTOP' in link.sent for link in self.links.values()))

    def test_unknown_to_free_and_disk_failure_cannot_confirm(self):
        proposal = self.rows[self.payload['proposal_map_id']]
        raw = json.dumps(dict(proposal['geometry'],cells=[0,0])).encode()
        self.files[proposal['object_path']] = raw
        proposal['sha256'] = self.payload['proposal_sha256'] = hashlib.sha256(raw).hexdigest()
        self.assertEqual(self.processor.process([self.row()]),['rejected'])
        self.assertEqual(self.writes,[])
        self.store.enqueue = lambda *args,**kwargs:False
        raw = json.dumps(dict(proposal['geometry'],cells=[0,-1])).encode()
        proposal['sha256'] = self.payload['proposal_sha256'] = hashlib.sha256(raw).hexdigest()
        self.files[proposal['object_path']] = raw
        self.assertEqual(self.processor.process([self.row()]),['rejected'])
        self.assertIsNone(self.store.active_config())
