"""동기화 작업자 전용 SQLite. 제어 잠금 안에서 디스크 메서드를 호출하지 않습니다."""
from dataclasses import dataclass
import hashlib
import json
import sqlite3
import uuid
from host.command_journal import CommandJournal

META_LIMIT = 16_384
CONFIG_LIMIT = 4 * 1024 * 1024
UPLOAD_TABLES = {'robot_status','alerts','events','operator_actions','maps','zones','waypoints',
                 'routes','routines','routine_runs'}


def encode(value, limit=META_LIMIT):
    stack = [(value, 0)]
    nodes = 0
    while stack:
        item, depth = stack.pop()
        nodes += 1
        if depth > 32 or nodes > limit:
            raise ValueError('metadata nesting or size exceeded')
        if isinstance(item, dict):
            if any(not isinstance(key, str) for key in item):
                raise ValueError('JSON keys must be strings')
            stack.extend((child, depth+1) for child in item.values())
        elif isinstance(item, (list, tuple)):
            stack.extend((child, depth+1) for child in item)
    text = json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)
    if len(text.encode('utf-8')) > limit:
        raise ValueError('metadata too large')
    return text


def digest_config(value):
    return hashlib.sha256(encode(value, CONFIG_LIMIT).encode('utf-8')).hexdigest()


def identity(value):
    if not isinstance(value, str) or str(uuid.UUID(value)) != value:
        raise ValueError('canonical UUID required')
    return value


@dataclass(frozen=True)
class Pending:
    seq: int
    event_id: str
    table: str
    operation: str
    row: dict


class Store:
    def __init__(self, path, hub_id, device_id, *, capacity=10_000):
        self.hub_id, self.device_id = identity(hub_id), identity(device_id)
        if type(capacity) is not int or not 1 <= capacity <= 100_000:
            raise ValueError('invalid outbox capacity')
        self.capacity, self.failures = capacity, 0
        self._db = sqlite3.connect(path, timeout=.05, isolation_level=None)
        try:
            self._db.execute('PRAGMA journal_mode=WAL')
            self._db.execute('PRAGMA synchronous=FULL')
            self._db.executescript('''
                CREATE TABLE IF NOT EXISTS hub_identity (singleton INTEGER PRIMARY KEY CHECK(singleton=1), hub TEXT NOT NULL, device TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS sync_outbox (seq INTEGER PRIMARY KEY AUTOINCREMENT,
                  event_id TEXT UNIQUE NOT NULL, table_name TEXT NOT NULL, operation TEXT NOT NULL, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS config_copies (version INTEGER PRIMARY KEY, digest TEXT NOT NULL, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS active_config (singleton INTEGER PRIMARY KEY CHECK(singleton=1), version INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS hub_status (robot TEXT PRIMARY KEY, payload TEXT NOT NULL);
            ''')
            self._db.execute('INSERT OR IGNORE INTO hub_identity VALUES (1,?,?)', (self.hub_id,self.device_id))
            existing = self._db.execute('SELECT hub,device FROM hub_identity WHERE singleton=1').fetchone()
            if existing != (self.hub_id, self.device_id):
                raise ValueError('database belongs to another hub/device')
            self.journal = CommandJournal(path)
        except Exception:
            self._db.close()
            raise

    def _transaction(self, work):
        try:
            self._db.execute('BEGIN IMMEDIATE')
            work()
            self._db.execute('COMMIT')
            return True
        except (sqlite3.Error, ValueError, TypeError, OverflowError, RecursionError):
            try:
                if self._db.in_transaction:
                    self._db.execute('ROLLBACK')
            except sqlite3.Error:
                pass
            self.failures += 1
            return False

    def _prepare(self, table, row, operation, event_id):
        if (operation == 'upsert' and table not in UPLOAD_TABLES) or operation not in ('upsert','command_result'):
            raise ValueError('upload not allowed')
        if not isinstance(row, dict) or row.get('hub_id') != self.hub_id:
            raise ValueError('hub mismatch')
        identity(row.get('id'))
        if operation == 'command_result':
            if (table != 'commands' or set(row) != {'id','hub_id','status','result','updated_at'}
                    or row['status'] not in ('accepted','rejected','expired','done') or not isinstance(row['result'], dict)):
                raise ValueError('invalid command result')
        elif row.get('device_id') != self.device_id:
            raise ValueError('device mismatch')
        if operation == 'upsert' and (not isinstance(row.get('created_at'),str) or not row['created_at']):
            raise ValueError('stable created_at required for retry')
        if row.get('robot_id') not in (None,'A','B'):
            raise ValueError('invalid robot')
        return identity(event_id or str(uuid.uuid4())), encode(row)

    def _insert(self, event_id, table, operation, text):
        old = self._db.execute('SELECT table_name,operation,payload FROM sync_outbox WHERE event_id=?', (event_id,)).fetchone()
        if old:
            if old != (table,operation,text):
                raise ValueError('outbox id collision')
            return
        if self._db.execute('SELECT COUNT(*) FROM sync_outbox').fetchone()[0] >= self.capacity:
            raise ValueError('outbox full')
        self._db.execute('INSERT INTO sync_outbox(event_id,table_name,operation,payload) VALUES (?,?,?,?)',
                         (event_id,table,operation,text))

    def enqueue(self, table, row, *, operation='upsert', event_id=None):
        def write():
            key, text = self._prepare(table,row,operation,event_id)
            self._insert(key,table,operation,text)
        return self._transaction(write)

    def peek(self):
        row = self._db.execute('SELECT seq,event_id,table_name,operation,payload FROM sync_outbox ORDER BY seq LIMIT 1').fetchone()
        return Pending(*row[:4], json.loads(row[4])) if row else None

    def acknowledge(self, seq, event_id):
        def write():
            if type(seq) is not int or seq < 1:
                raise ValueError('invalid acknowledgement')
            identity(event_id)
            head = self.peek()
            if head is None or (head.seq,head.event_id) != (seq,event_id):
                raise ValueError('only queue head may be acknowledged')
            self._db.execute('DELETE FROM sync_outbox WHERE seq=? AND event_id=?', (seq,event_id))
        return self._transaction(write)

    def save_status(self, robot, row):
        def write():
            if robot not in ('A','B') or not isinstance(row, dict) or row.get('robot_id') != robot:
                raise ValueError('status robot mismatch')
            key, text = self._prepare('robot_status',row,'upsert',None)
            self._insert(key,'robot_status','upsert',text)
            self._db.execute('INSERT OR REPLACE INTO hub_status VALUES (?,?)', (robot,text))
        return self._transaction(write)

    def status(self, robot):
        row = self._db.execute('SELECT payload FROM hub_status WHERE robot=?', (robot,)).fetchone()
        return json.loads(row[0]) if row else None

    def activate_config(self, version, value, expected_digest):
        def write():
            if type(version) is not int or version < 1 or not isinstance(value, dict) or value.get('state') != 'confirmed':
                raise ValueError('confirmed config required')
            if value.get('hub_id') != self.hub_id:
                raise ValueError('config hub mismatch')
            text = encode(value,CONFIG_LIMIT)
            digest = hashlib.sha256(text.encode('utf-8')).hexdigest()
            if expected_digest != digest:
                raise ValueError('config digest mismatch')
            active = self._db.execute('SELECT version FROM active_config WHERE singleton=1').fetchone()
            old = self._db.execute('SELECT digest FROM config_copies WHERE version=?', (version,)).fetchone()
            if (active and version < active[0]) or (old and old[0] != digest):
                raise ValueError('old version or changed confirmed config')
            self._db.execute('INSERT OR IGNORE INTO config_copies VALUES (?,?,?)', (version,digest,text))
            self._db.execute('INSERT OR REPLACE INTO active_config VALUES (1,?)', (version,))
        return self._transaction(write)

    def active_config(self):
        row = self._db.execute('SELECT c.version,c.digest,c.payload FROM config_copies c JOIN active_config a ON c.version=a.version').fetchone()
        return {'version':row[0], 'digest':row[1], 'value':json.loads(row[2])} if row else None

    def close(self):
        try:
            self.journal.close()
        finally:
            self._db.close()
