"""SQL 실행 없이 문서/정의/권한 선언 계약만 검사합니다. 실제 RLS 시험이 아닙니다."""
from pathlib import Path
import re
import unittest
from host.command_envelope import FIELDS

ROOT = Path(__file__).resolve().parents[2]
TABLES = {'devices','robot_status','alerts','events','operator_actions','commands','notifications',
          'maps','zones','waypoints','routes','routines','routine_runs'}


class SchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sql = (ROOT / 'supabase/migrations/0001_init.sql').read_text(encoding='utf-8')
        cls.docs = (ROOT / 'docs/supabase-schema.md').read_text(encoding='utf-8')
        cls.bodies = dict(re.findall(r'create table public\.(\w+) \((.*?)\n\);', cls.sql, re.S))

    def test_all_required_tables_have_uuid_and_rls(self):
        self.assertEqual(set(self.bodies), TABLES)
        enabled = set(re.findall(r'alter table public\.(\w+) enable row level security;', self.sql))
        self.assertEqual(enabled, TABLES)
        for table, body in self.bodies.items():
            with self.subTest(table=table):
                self.assertIn('id uuid primary key default gen_random_uuid()', body)
                for column in ('hub_id','robot_id','device_id','created_at'):
                    self.assertRegex(body, r'\b' + column + r'\s')

    def test_documented_columns_exactly_match_sql(self):
        rows = re.findall(r'^\| `(\w+)` \| (.*?) \|', self.docs, re.M)
        self.assertEqual({name for name, _ in rows}, TABLES)
        common = {'id','hub_id','robot_id','device_id','created_at'}
        for name, extras in rows:
            actual = set(re.findall(r'(?:^|,)\s*(\w+)\s+(?:uuid|text|boolean|integer|jsonb|timestamptz)\b',
                                    self.bodies[name], re.M))
            self.assertEqual(actual, common | set(re.findall(r'`(\w+)`', extras)), name)

    def test_command_envelope_and_result_column_permissions(self):
        body = self.bodies['commands']
        for field in FIELDS:
            self.assertRegex(body, r'\b' + field + r'\s')
        self.assertIn("('estop','reset','operator','map_confirm')", body)
        self.assertIn("jsonb_array_length(payload->'approved_clearings')<=128",body)
        self.assertIn("payload->'confirmed'='true'::jsonb", body)
        self.assertIn('is true)', body)  # CHECK에서 NULL로 통과하지 않게 명시
        self.assertIn('grant update(status,result,updated_at) on public.commands', self.sql)
        self.assertNotIn('grant update on public.commands', self.sql)
        self.assertIn("status='pending' and result='{}'::jsonb", self.sql)

    def test_authority_registry_is_not_client_writable(self):
        self.assertIn("security definer set search_path=''", self.sql)
        self.assertIn('d.auth_user_id=(select auth.uid())', self.sql)
        self.assertIn('revoke all on public.%I from public, anon, authenticated', self.sql)
        self.assertIn("array['robot_status','alerts','events','operator_actions','maps'", self.sql)
        self.assertNotRegex(self.sql, r'grant (?:insert|update|delete).*on public.devices')
        self.assertNotIn('for all', self.sql.lower())
        self.assertIn('foreign key(hub_id,map_id)', self.sql)
        self.assertIn('if to_jsonb(new)=to_jsonb(old) then', self.sql)
