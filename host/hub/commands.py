"""Validated cloud commands; disk work stays outside the core lock."""
from datetime import datetime, timezone
import math
import time
import uuid
from dashboard.core.state import OPERATOR_EVENTS
from host.command_envelope import FIELDS, validate_envelope
from host.hub.store import encode, identity


class ResetContexts:
    """Public, single-use state confirmation, not an authentication credential."""
    def __init__(self, core, clock=time.monotonic):
        self.core, self.clock = core, clock
        self.prefix, self.seq, self.entries = uuid.uuid4().hex, 0, {}

    def issue(self, robot):
        link = self.core.links.get(robot)
        latest = getattr(link, 'latest', None)
        now = self.clock()
        if (link is None or not math.isfinite(now) or not link.fresh()
                or latest is None or not latest.latched):
            self.entries.pop(robot, None)
            return None
        fingerprint = (self.core.reset_epochs[robot],getattr(latest,'boot_id',None),
                       latest.reason,bool(getattr(link,'emergency',False)))
        old = self.entries.get(robot)
        if old is None or old[1] != fingerprint or not 0 <= now-old[2] < 5:
            self.seq += 1
            old = (self.prefix+':'+str(self.seq),fingerprint,now)
            self.entries[robot] = old
        return old[0]

    def consume(self, robot, supplied):
        current = self.issue(robot)
        if current is None or current != supplied:
            raise ValueError('reset_context_changed')
        self.entries.pop(robot, None)


class Processor:
    def __init__(self, core, store, authorize, lock, *, wall=time.time,
                 clock=time.monotonic, clock_trusted=lambda:False, map_confirmer=None):
        # authorize(device_id) must use a trusted, current device registry, never row claims.
        self.core, self.store, self.authorize, self.lock = core, store, authorize, lock
        self.wall, self.clock_trusted = wall, clock_trusted
        self.contexts = ResetContexts(core,clock)
        self.waiting = {}
        self.map_confirmer = map_confirmer
        self.report_failures = 0

    def reset_contexts(self):
        with self.lock:
            return {robot:self.contexts.issue(robot) for robot in ('A','B')}

    def _validate(self, row):
        if not isinstance(row,dict) or not FIELDS <= set(row) or set(row)-FIELDS-{'status','result','updated_at'}:
            raise ValueError('invalid row')
        envelope = {key:row[key] for key in FIELDS}
        # PostgreSQL REST may serialize timestamptz as +00:00 instead of Z.
        for key in ('created_at','expires_at'):
            value = envelope[key]
            if isinstance(value,str) and value.endswith('+00:00'):
                envelope[key] = value[:-6]+'Z'
        permissions = self.authorize(envelope['device_id'])
        return validate_envelope(encode(envelope).encode('utf-8'),hub_id=self.store.hub_id,
            authenticated_device=envelope['device_id'],permissions=permissions,
            now_utc=self.wall(),clock_trusted=self.clock_trusted(),operator_events=OPERATOR_EVENTS)

    def _report(self, row, status, reason):
        try:
            identity(row['id'])
            if row['hub_id'] != self.store.hub_id:
                return
            result = dict(id=row['id'],hub_id=self.store.hub_id,status=status,
                          result={'reason':reason},
                          updated_at=datetime.fromtimestamp(self.wall(),timezone.utc).isoformat().replace('+00:00','Z'))
            if not self.store.enqueue('commands',result,operation='command_result'):
                self.report_failures += 1
        except Exception:
            self.report_failures += 1

    def _finish(self, command, status, reason):
        try:
            self.store.journal.complete(command,status,reason)
        except Exception:
            self.report_failures += 1

    def process(self, rows):
        if not isinstance(rows,list) or len(rows)>200:
            raise ValueError('bounded batch required')
        outcomes = []
        stopped = False
        for row in sorted(rows,key=lambda item:0 if isinstance(item,dict) and item.get('kind')=='estop' else 1):
            try:
                command = self._validate(row)
            except Exception as error:
                expired = isinstance(error,ValueError) and str(error)=='command expired or from future'
                status = 'expired' if expired else 'rejected'
                self._report(row,status,'invalid_envelope')
                outcomes.append(status)
                continue
            if command.kind == 'estop':
                # No journal/outbox access until all robot stop attempts have happened.
                with self.lock:
                    self.core.estop_all(source='supabase')
                stopped = True
                self._report(row,'done','stop_dispatched')
                outcomes.append('done')
                continue
            if stopped:
                self._report(row,'rejected','stop_in_same_batch')
                outcomes.append('rejected')
                continue
            try:
                fresh = self.store.journal.claim(command)
                if not fresh:
                    old = self.store.journal.result(command)
                    status = ('accepted' if command.id in self.waiting else
                              old['status'] if old['status'] in ('done','rejected') else 'rejected')
                    self._report(row,status,old['reason'] if status!='rejected' else 'already_reserved')
                    outcomes.append(status)
                    continue
            except Exception:
                self._report(row,'rejected','journal_unavailable')
                outcomes.append('rejected')
                continue
            self._report(row,'accepted','validated')
            try:
                if command.kind == 'map_confirm':
                    # File/SQLite work never holds the robot control lock.
                    if (self.map_confirmer is None or not self.clock_trusted()
                            or not command.created_at <= self.wall() < command.expires_at):
                        raise ValueError('map_confirmation_unavailable')
                    self.map_confirmer(command)
                    self._finish(command,'done','map_confirmation_queued')
                    self._report(row,'done','map_confirmation_queued')
                    outcomes.append('done')
                    continue
                with self.lock:
                    # A journal write may take time: recheck expiry before execution.
                    if not self.clock_trusted() or not command.created_at <= self.wall() < command.expires_at:
                        raise ValueError('expired_before_execution')
                    if command.kind == 'reset':
                        self.contexts.consume(command.robot_id,dict(command.payload)['reset_context'])
                        result = self.core.reset_latch(command.robot_id,confirmed=True)
                    else:
                        result = self.core.operator(dict(command.payload)['event'])
                    epoch = self.core.reset_epochs.get(command.robot_id)
                    latest = getattr(self.core.links.get(command.robot_id),'latest',None)
                    boot = getattr(latest,'boot_id',None)
                if not result.get('ok'):
                    raise ValueError('core_rejected')
                if command.kind == 'reset':
                    self.waiting[command.id] = (command,row,epoch,boot)
                    outcomes.append('accepted')  # Do not claim a cleared latch before telemetry.
                else:
                    self._finish(command,'done','intent_dispatched')
                    self._report(row,'done','intent_dispatched')
                    outcomes.append('done')
            except Exception:
                self._finish(command,'rejected','execution_rejected')
                self._report(row,'rejected','execution_rejected')
                outcomes.append('rejected')
        return outcomes

    def reconcile_resets(self):
        for key,(command,row,epoch,boot) in list(self.waiting.items()):
            with self.lock:
                link = self.core.links[command.robot_id]
                latest = getattr(link,'latest',None)
                changed = (self.core.reset_epochs[command.robot_id] != epoch
                           or (latest is not None and getattr(latest,'boot_id',None)!=boot))
                done = not changed and link.fresh() and latest is not None and not latest.latched
            if done or changed or self.wall() >= command.expires_at:
                status,reason = ('done','telemetry_unlatched') if done else ('rejected','reset_not_confirmed')
                self._finish(command,status,reason)
                self._report(row,status,reason)
                self.waiting.pop(key)
