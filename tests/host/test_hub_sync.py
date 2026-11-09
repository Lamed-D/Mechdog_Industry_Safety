import io
import json
import unittest
import uuid
from urllib.parse import parse_qs, urlsplit
from host.hub.store import Store
from host.hub.sync import Sync, RestGateway
from tools.mock.fake_supabase import FakeSupabase

HUB = '00000000-0000-4000-8000-000000000001'


class Response(io.BytesIO):
    status = 200


class Opener:
    def __init__(self):
        self.requests = []
        self.result = []

    def open(self, request, timeout):
        self.requests.append((request, timeout))
        return Response(json.dumps(self.result).encode())


class SyncTests(unittest.TestCase):
    def setUp(self):
        self.now = 0
        self.store = Store(':memory:',HUB,HUB)
        self.addCleanup(self.store.close)
        self.cloud = FakeSupabase()
        self.sync = Sync(self.store,self.cloud,clock=lambda:self.now)

    def row(self):
        return dict(id=str(uuid.uuid4()),hub_id=HUB,device_id=HUB,
                    created_at='2026-01-01T00:00:00Z',kind='synthetic',detail={})

    def test_lost_ack_retry_same_uuid_and_fifo(self):
        first, second = self.row(), self.row()
        self.store.enqueue('events',first)
        self.store.enqueue('events',second)
        self.cloud.fail_after_write = True
        self.sync.tick()
        self.assertEqual(len(self.cloud.rows),1)
        self.sync.tick()  # before retry deadline
        self.assertEqual(len(self.cloud.uploads),1)
        self.now = 1
        self.cloud.fail_after_write = False
        self.sync.tick()
        self.assertEqual(self.cloud.uploads[0],self.cloud.uploads[1])
        self.assertEqual(self.store.peek().row['id'],second['id'])
        self.sync.tick()
        self.assertIsNone(self.store.peek())
        self.assertEqual(len(self.cloud.rows),2)

    def test_backoff_poll_and_internet_timeout(self):
        self.store.enqueue('events',self.row())
        self.cloud.offline = True
        self.sync.tick()
        self.assertFalse(self.sync.internet_ok())
        self.now = 1
        self.sync.tick()
        self.assertEqual(self.sync._upload_at,3)
        self.cloud.offline = False
        self.cloud.pending = [dict(id='normal',hub_id=HUB,kind='operator'),
                              dict(id='stop',hub_id=HUB,kind='estop')]
        self.now = 2
        self.assertEqual(self.sync.tick()[0]['id'],'stop')
        self.assertIsNotNone(self.store.peek())  # upload still backs off
        self.assertTrue(self.sync.internet_ok())
        self.now = 12
        self.assertFalse(self.sync.internet_ok())
        self.now = 1
        with self.assertRaises(ValueError):
            self.sync.tick()

    def test_local_ack_failure_retries_without_dropping(self):
        self.store.enqueue('events',self.row())
        original = self.store.acknowledge
        self.store.acknowledge = lambda *args:False
        self.sync.tick()
        self.assertIsNotNone(self.store.peek())
        self.store.acknowledge = original
        self.now = 1
        self.sync.tick()
        self.assertEqual(len(self.cloud.rows),1)
        self.assertIsNone(self.store.peek())

    def test_fetched_stop_skips_upload_and_survives_normal_query_failure(self):
        self.store.enqueue('events',self.row())
        self.cloud.pending = [dict(id='stop',hub_id=HUB,kind='estop')]
        self.assertEqual(self.sync.tick()[0]['id'],'stop')
        self.assertEqual(self.cloud.uploads,[])
        rest = RestGateway('https://synthetic.invalid','placeholder',lambda:'t',
                           hub_id=HUB,device_id=HUB,opener=Opener())
        def request(table, query):
            if query['kind'] == 'eq.estop':
                return self.cloud.pending
            raise ConnectionError('synthetic normal query failure')
        rest._request = request
        self.assertEqual(rest.commands(HUB),self.cloud.pending)

    def test_rest_requests_are_injected_scoped_and_require_uuid_ack(self):
        opener = Opener()
        rest = RestGateway('https://synthetic.invalid','placeholder',lambda:'synthetic-token',
                           hub_id=HUB,device_id=HUB,opener=opener)
        row = self.row()
        self.store.enqueue('events',row)
        with self.assertRaises(ValueError):
            rest.upload(self.store.peek())  # empty RLS result must not erase queue
        opener.result = [{'id':row['id']}]
        rest.upload(self.store.peek())
        request, timeout = opener.requests[-1]
        self.assertEqual(timeout,2)
        self.assertEqual(request.method,'POST')
        query = parse_qs(urlsplit(request.full_url).query)
        self.assertEqual(query['hub_id'],['eq.'+HUB])
        self.assertEqual(query['on_conflict'],['id'])
        self.assertEqual(json.loads(request.data),row)
        opener.result = []
        self.assertEqual(rest.commands(HUB),[])
        queries = [parse_qs(urlsplit(req.full_url).query) for req,_ in opener.requests[-2:]]
        self.assertEqual([q['kind'][0] for q in queries],['eq.estop','neq.estop'])

    def test_command_patch_does_not_write_envelope(self):
        opener = Opener()
        rest = RestGateway('https://synthetic.invalid','placeholder',lambda:'synthetic-token',
                           hub_id=HUB,device_id=HUB,opener=opener)
        row = dict(id=str(uuid.uuid4()),hub_id=HUB,status='done',result={},updated_at='synthetic')
        self.store.enqueue('commands',row,operation='command_result')
        opener.result = [{'id':row['id']}]
        rest.upload(self.store.peek())
        request,_ = opener.requests[-1]
        self.assertEqual(request.method,'PATCH')
        self.assertEqual(set(json.loads(request.data)),{'status','result','updated_at'})

    def test_credentials_origin_and_response_validation(self):
        for url in ('http://synthetic.invalid','https://a@synthetic.invalid',
                    'https://synthetic.invalid/path','https://synthetic.invalid?token=x'):
            with self.assertRaises(ValueError):
                RestGateway(url,'placeholder',lambda:'t',hub_id=HUB,device_id=HUB)
        opener = Opener()
        rest = RestGateway('https://synthetic.invalid','placeholder',lambda:'bad\ntoken',
                           hub_id=HUB,device_id=HUB,opener=opener)
        with self.assertRaises(ValueError):
            rest.commands(HUB)
        self.assertEqual(opener.requests,[])
        rest.token_provider = lambda:'t'
        opener.result = {'not':'rows'}
        with self.assertRaises(ValueError):
            rest.commands(HUB)
