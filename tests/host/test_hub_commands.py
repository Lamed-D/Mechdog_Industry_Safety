from datetime import datetime, timezone
import threading
import unittest
import uuid
from dashboard.web.run import build_sim
from host.hub.store import Store
from host.hub.commands import Processor

HUB = '00000000-0000-4000-8000-000000000001'
DEVICE = '00000000-0000-4000-8000-000000000002'


class ProcessorTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026,1,1,tzinfo=timezone.utc).timestamp()
        self.mono = 0
        self.core,self.links = build_sim(clock=lambda:self.mono,wall=lambda:self.now)
        self.addCleanup(self.core.log.close)
        for link in self.links.values():
            link.step()
        self.store = Store(':memory:',HUB,HUB)
        self.addCleanup(self.store.close)
        self.trusted = True
        self.processor = Processor(self.core,self.store,
            lambda device:('estop','operator','reset') if device==DEVICE else (),
            threading.RLock(),wall=lambda:self.now,clock=lambda:self.mono,
            clock_trusted=lambda:self.trusted)

    def row(self, kind='operator', **updates):
        row = dict(v=1,id=str(uuid.uuid4()),hub_id=HUB,device_id=DEVICE,robot_id=None,
                   kind=kind,payload={'event':'operator_ack'} if kind=='operator' else {},
                   created_at='2026-01-01T00:00:00+00:00',expires_at='2026-01-01T00:00:10+00:00')
        row.update(updates)
        return row

    def reset(self):
        return self.row('reset',robot_id='A',payload=dict(confirmed=True,
            reset_context=self.processor.reset_contexts()['A']))

    def test_stop_ignores_expiry_clock_and_broken_storage_and_goes_first(self):
        self.now += 100
        self.trusted = False
        calls = []
        def broken(*args,**kwargs):
            self.assertIn('ESTOP',self.links['A'].sent)
            self.assertIn('ESTOP',self.links['B'].sent)
            calls.append('disk')
            raise OSError('synthetic disk failure')
        self.store.enqueue = broken
        self.store.journal.claim = lambda command:self.fail('ESTOP must not use journal')
        self.assertEqual(self.processor.process([self.row('estop')]),['done'])
        self.assertEqual(calls,['disk'])

    def test_same_batch_stop_blocks_reset_and_operator(self):
        reset = self.reset()
        outcomes = self.processor.process([reset,self.row(),self.row('estop')])
        self.assertEqual(outcomes,['done','rejected','rejected'])
        self.assertNotIn('RESET',self.links['A'].sent)

    def test_operator_duplicate_runs_only_once_and_changed_id_is_rejected(self):
        calls = []
        self.core.operator = lambda event:(calls.append(event) or {'ok':True})
        row = self.row()
        self.assertEqual(self.processor.process([row,row]),['done','done'])
        self.assertEqual(calls,['operator_ack'])
        row['payload'] = {'event':'start_patrol'}
        self.assertEqual(self.processor.process([row]),['rejected'])
        self.assertEqual(len(calls),1)

    def test_reset_waits_for_fresh_unlatched_telemetry(self):
        row = self.reset()
        self.assertEqual(self.processor.process([row,row]),['accepted','accepted'])
        self.assertEqual(self.links['A'].sent,['RESET'])
        self.processor.reconcile_resets()
        self.assertEqual(len(self.processor.waiting),1)
        self.links['A'].step()
        self.processor.reconcile_resets()
        self.assertEqual(self.processor.waiting,{})
        self.assertEqual(self.processor.process([row]),['done'])

    def test_new_stop_invalidates_context_and_pending_reset(self):
        old = self.reset()
        self.core.estop_all()
        self.assertEqual(self.processor.process([old]),['rejected'])
        row = self.reset()
        self.assertEqual(self.processor.process([row]),['accepted'])
        self.core.estop_all()
        self.processor.reconcile_resets()
        self.assertEqual(self.processor.waiting,{})
        self.assertEqual(self.processor.process([row]),['rejected'])

    def test_permissions_expiry_confirmation_and_journal_failure(self):
        self.assertEqual(self.processor.process([self.row(device_id='unregistered')]),['rejected'])
        row = self.reset()
        row['payload']['confirmed'] = False
        self.assertEqual(self.processor.process([row]),['rejected'])
        self.now += 10
        self.assertEqual(self.processor.process([self.row()]),['expired'])
        self.now -= 10
        self.store.journal.claim = lambda command:(_ for _ in ()).throw(OSError('disk'))
        self.assertEqual(self.processor.process([self.reset()]),['rejected'])
        self.assertEqual(self.links['A'].sent,[])

    def test_expiry_rechecked_after_journal_and_reserved_not_reexecuted(self):
        row = self.row()
        command = self.processor._validate(row)
        self.store.journal.claim(command)
        self.core.operator = lambda event:self.fail('reserved must not execute')
        self.assertEqual(self.processor.process([row]),['rejected'])
        original = self.store.journal.claim
        def slow(command):
            result = original(command)
            self.now += 11
            return result
        self.store.journal.claim = slow
        self.assertEqual(self.processor.process([self.row()]),['rejected'])
