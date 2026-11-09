"""Outbound-only cloud synchronization; call from a dedicated worker, never control locks."""
import json
import math
import time
from typing import Protocol
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
from host.hub.store import encode, identity


class Gateway(Protocol):
    def upload(self, pending): ...
    def commands(self, hub_id): ...


class Sync:
    def __init__(self, store, gateway, *, clock=time.monotonic, retry_max=60):
        if not math.isfinite(retry_max) or retry_max < 1:
            raise ValueError('invalid retry maximum')
        self.store, self.gateway, self.clock = store, gateway, clock
        self.retry_max = retry_max
        self.last_success = None
        self.failures = 0
        self._upload_at = self._poll_at = 0
        self._delay = 1
        self._last_tick = None

    def tick(self):
        """At most one FIFO upload and one command poll; caller executes returned commands."""
        now = self.clock()
        if not math.isfinite(now) or (self._last_tick is not None and now < self._last_tick):
            raise ValueError('monotonic clock required')
        self._last_tick = now
        commands = []
        # Poll independently of a failed upload: an outbox error must not starve ESTOP.
        if now >= self._poll_at:
            self._poll_at = now + 1
            try:
                commands = self.gateway.commands(self.store.hub_id)
                if not isinstance(commands, list) or len(commands) > 200:
                    raise ValueError('invalid command batch')
                self.last_success = self.clock()
            except Exception:
                self.failures += 1
                commands = []
        if any(isinstance(row, dict) and row.get('kind') == 'estop' for row in commands):
            return commands  # Do not delay a fetched stop behind an upload timeout.
        if now >= self._upload_at:
            try:
                pending = self.store.peek()
                if pending:
                    self.gateway.upload(pending)
                    self.last_success = self.clock()
                    if not self.store.acknowledge(pending.seq, pending.event_id):
                        raise ValueError('local acknowledgement failed')
                self._delay = 1
                self._upload_at = self.clock()
            except Exception:
                self.failures += 1
                self._upload_at = self.clock() + self._delay
                self._delay = min(self.retry_max, self._delay * 2)
        return commands

    def internet_ok(self, *, timeout=10):
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError('invalid timeout')
        now = self.clock()
        return (self.last_success is not None and math.isfinite(now)
                and 0 <= now - self.last_success < timeout)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never forward bearer credentials to a redirect target.
        return None


class RestGateway:
    """Explicitly configured REST adapter. Construction does not connect or read credentials."""
    def __init__(self, url, api_key, token_provider, *, hub_id, device_id, timeout=2, opener=None):
        parsed = urlsplit(url)
        if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
                or parsed.query or parsed.fragment or parsed.path not in ('', '/')):
            raise ValueError('HTTPS project origin required')
        if not isinstance(api_key, str) or not api_key or any(c in api_key for c in '\r\n'):
            raise ValueError('API key required')
        if not callable(token_provider) or not math.isfinite(timeout) or not 0 < timeout <= 10:
            raise ValueError('token provider and bounded timeout required')
        self.base, self.api_key = url.rstrip('/') + '/rest/v1/', api_key
        self.token_provider, self.timeout = token_provider, timeout
        self.hub_id, self.device_id = identity(hub_id), identity(device_id)
        self.opener = opener or build_opener(NoRedirect())

    def _request(self, table, query, method='GET', row=None, prefer=None):
        token = self.token_provider()
        if not isinstance(token, str) or not token or any(c in token for c in '\r\n'):
            raise ValueError('active user access token required')
        headers = {'apikey':self.api_key, 'Authorization':'Bearer '+token,
                   'Accept':'application/json', 'Content-Type':'application/json'}
        if prefer:
            headers['Prefer'] = prefer
        req = Request(self.base+table+'?'+urlencode(query),
                      data=None if row is None else encode(row).encode('utf-8'),
                      headers=headers, method=method)
        with self.opener.open(req, timeout=self.timeout) as response:
            if not 200 <= response.status < 300:
                raise ValueError('REST response rejected')
            raw = response.read(1_048_577)
            if len(raw) > 1_048_576:
                raise ValueError('REST response too large')
            value = json.loads(raw) if raw else []
        if not isinstance(value, list):
            raise ValueError('REST rows required')
        return value

    def upload(self, pending):
        # Revalidate even if a caller constructs Pending without Store.
        from host.hub.store import UPLOAD_TABLES
        row = pending.row
        identity(row.get('id'))
        if row.get('hub_id') != self.hub_id:
            raise ValueError('hub mismatch')
        query = {'select':'id', 'hub_id':'eq.'+self.hub_id}
        if pending.operation == 'command_result':
            if (pending.table != 'commands' or set(row) != {'id','hub_id','status','result','updated_at'}
                    or row['status'] not in ('accepted','rejected','expired','done')):
                raise ValueError('invalid command result')
            query['id'] = 'eq.'+row['id']
            payload = {key:row[key] for key in ('status','result','updated_at')}
            result = self._request('commands',query,'PATCH',payload,'return=representation')
        else:
            if (pending.operation != 'upsert' or pending.table not in UPLOAD_TABLES
                    or row.get('device_id') != self.device_id or not row.get('created_at')):
                raise ValueError('invalid upload')
            query['on_conflict'] = 'id'
            result = self._request(pending.table,query,'POST',row,
                                   'resolution=merge-duplicates,return=representation')
        if result != [{'id':row['id']}]:
            raise ValueError('write not acknowledged by matching UUID')

    def commands(self, hub_id):
        if hub_id != self.hub_id:
            raise ValueError('hub mismatch')
        # Separate first query prevents old normal commands hiding a global stop.
        common = {'hub_id':'eq.'+hub_id,'status':'eq.pending','select':'*',
                  'order':'created_at.asc,id.asc','limit':'100'}
        stops = self._request('commands',dict(common,kind='eq.estop'))
        try:
            normal = self._request('commands',dict(common,kind='neq.estop'))
        except Exception:
            if stops:
                return stops  # A later normal-query failure must not discard fetched stops.
            raise
        return stops + normal
