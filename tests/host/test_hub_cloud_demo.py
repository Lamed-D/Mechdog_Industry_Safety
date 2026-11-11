import unittest
from unittest.mock import patch
from host.hub.store import Pending
from tools.mock.fake_supabase import FakeSupabase
from tools.mock.hub_cloud_demo import run_demo


class HubCloudDemoTests(unittest.TestCase):
    def test_both_finders_complete_cloud_policy_cycle_without_network(self):
        for finder in ('A','B'):
            with self.subTest(finder=finder), patch('socket.socket',side_effect=AssertionError('no sockets')):
                result = run_demo(finder)
                self.assertTrue(result['routine_started'])
                self.assertEqual(result['active_version'],2)
                self.assertEqual(result['alert_state'],'acked')
                self.assertEqual(result['ack_status'],'done')
                self.assertEqual(result['command_count'],4)
                self.assertEqual(result['phase'],'suspended')
                self.assertEqual(result['states'],{'A':'stopped','B':'stopped'})
                self.assertTrue(result['paused'])
                self.assertTrue(result['scheduler_held'])
                self.assertFalse(result['automatic_resume'])
                self.assertTrue(all(row['source']=='synthetic' and not row['hardware'] for row in result['timeline']))
                offline = next(row for row in result['timeline'] if row['event']=='offline_return')
                self.assertEqual(sum(intent['kind']=='return_server' for intent in offline['detail']['intents']),2)
                incident = next(row for row in result['timeline'] if row['event']=='incident')
                self.assertEqual([i['kind'] for i in incident['detail']['intents']],['stop','stop'])

    def test_missing_navigator_yields_stop_and_never_automatic_resume(self):
        result = run_demo(navigator_available=False)
        offline = next(row for row in result['timeline'] if row['event']=='offline_return')
        self.assertFalse(any(i['kind']=='return_server' for i in offline['detail']['intents']))
        self.assertEqual(sum(i['reason']=='navigator_unavailable' for i in offline['detail']['intents']),2)
        self.assertTrue(result['paused'])
        self.assertFalse(result['automatic_resume'])

    def test_fake_command_patch_preserves_envelope_and_stops_polling_completed_rows(self):
        cloud = FakeSupabase()
        row = dict(id='synthetic',hub_id='hub',kind='estop',payload={},status='pending')
        cloud.pending.append(row)
        cloud.upload(Pending(1,'result','commands','command_result',
            dict(id='synthetic',hub_id='hub',status='done',result={'reason':'stop_dispatched'})))
        self.assertEqual(cloud.rows['commands','synthetic']['kind'],'estop')
        self.assertEqual(cloud.commands('hub'),[])
        self.assertEqual(row['status'],'pending')
