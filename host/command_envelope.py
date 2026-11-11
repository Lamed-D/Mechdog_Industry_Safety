"""원격 조작 봉투 검사. 네트워크·키·로봇 실행에 연결하지 않습니다."""
from dataclasses import dataclass
from datetime import datetime
import json
import math
import re
import time
import uuid

MAX_BYTES = 4096
MAX_TTL_S = 10
FIELDS = {"v", "id", "hub_id", "device_id", "robot_id", "kind", "created_at", "expires_at", "payload"}


def _stamp(value):
    if not isinstance(value, str) or not re.fullmatch(
            r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,6})?Z", value):
        raise ValueError("UTC timestamp required")
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00").timestamp()
    except (ValueError, OverflowError, OSError) as error:
        raise ValueError("invalid UTC timestamp") from error


def _identity(value):
    return isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,64}", value) is not None


@dataclass(frozen=True)
class Command:
    id: str
    hub_id: str
    device_id: str
    robot_id: str | None
    kind: str
    created_at: float
    expires_at: float
    payload: tuple


def validate_envelope(raw, *, hub_id, authenticated_device, permissions, now_utc,
                      clock_trusted=False, operator_events=()):
    """호출자가 인증 채널에서 얻은 기기·권한을 별도로 넘깁니다. 본문 권한은 믿지 않습니다."""
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_BYTES:
        raise ValueError("invalid envelope size")
    try:
        def unique_pairs(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError("duplicate JSON key")
                result[key] = value
            return result
        row = json.loads(raw, object_pairs_hook=unique_pairs)
    except (UnicodeError, RecursionError) as error:
        raise ValueError("invalid envelope JSON") from error
    if not isinstance(row, dict) or set(row) != FIELDS:
        raise ValueError("invalid envelope fields")
    if type(row["v"]) is not int or row["v"] != 1:
        raise ValueError("unsupported envelope version")
    try:
        if not isinstance(row["id"], str) or str(uuid.UUID(row["id"])) != row["id"]:
            raise ValueError("invalid command id")
    except (AttributeError, TypeError) as error:
        raise ValueError("invalid command id") from error
    if (not _identity(row["hub_id"]) or row["hub_id"] != hub_id
            or not _identity(row["device_id"]) or row["device_id"] != authenticated_device):
        raise ValueError("command destination or authenticated device mismatch")
    kind, payload = row["kind"], row["payload"]
    if not isinstance(kind, str) or kind not in ("estop", "reset", "operator", "map_confirm") or kind not in permissions:
        raise ValueError("command not permitted")
    if not isinstance(payload, dict):
        raise ValueError("invalid command payload")
    if kind == "reset":
        if (row["robot_id"] not in ("A", "B") or set(payload) != {"confirmed", "reset_context"}
                or payload["confirmed"] is not True or not isinstance(payload["reset_context"], str)
                or not re.fullmatch(r"[a-f0-9]{32}:[1-9][0-9]{0,15}", payload["reset_context"])):
            raise ValueError("human confirmation and robot required")
    elif row["robot_id"] is not None:
        raise ValueError("unexpected robot target")
    elif kind == "estop" and payload:
        raise ValueError("unexpected estop payload")
    elif kind == "operator":
        if (set(payload) != {"event"} or not isinstance(payload["event"], str)
                or payload["event"] not in operator_events):
            raise ValueError("operator event not allowed")
    elif kind == "map_confirm":
        required = {'base_map_id','proposal_map_id','base_sha256','proposal_sha256','approved_clearings'}
        if set(payload) != required:
            raise ValueError('invalid map confirmation fields')
        for key in ('base_map_id','proposal_map_id'):
            if not isinstance(payload[key],str) or str(uuid.UUID(payload[key])) != payload[key]:
                raise ValueError('canonical map UUID required')
        clearings = payload['approved_clearings']
        if (payload['base_map_id'] == payload['proposal_map_id']
                or any(not isinstance(payload[key],str) or not re.fullmatch('[a-f0-9]{64}',payload[key])
                       for key in ('base_sha256','proposal_sha256'))
                or not isinstance(clearings,list) or len(clearings)>128
                or any(type(i) is not int or not 0<=i<1_000_000 for i in clearings)
                or len(set(clearings))!=len(clearings)):
            raise ValueError('invalid map confirmation')
        payload['approved_clearings'] = tuple(clearings)
    created, expires = _stamp(row["created_at"]), _stamp(row["expires_at"])
    if not 0 < expires - created <= MAX_TTL_S:
        raise ValueError("invalid command lifetime")
    if kind != "estop":
        if clock_trusted is not True or isinstance(now_utc, bool) or not isinstance(now_utc, (int, float)) or not math.isfinite(now_utc):
            raise ValueError("trusted UTC clock required")
        if not created <= now_utc < expires:
            raise ValueError("command expired or from future")
    return Command(row["id"], hub_id, authenticated_device, row["robot_id"], kind,
                   created, expires, tuple(sorted(payload.items())))


class ReplayWindow:
    """짧은 재전달 억제. 영속 저널을 대신하지 않습니다."""
    def __init__(self, capacity=1024, clock=time.monotonic):
        if type(capacity) is not int or not 1 <= capacity <= 100_000:
            raise ValueError("invalid replay capacity")
        self.capacity, self.clock = capacity, clock
        self._seen = {}
        self._last = -math.inf

    def admit(self, command):
        if not isinstance(command, Command):
            raise ValueError("validated Command required")
        if command.kind == "estop":
            return True  # 지연·중복이어도 정지를 막지 않습니다.
        now = self.clock()
        if isinstance(now, bool) or not isinstance(now, (int, float)) or not math.isfinite(now) or now < self._last:
            raise ValueError("invalid monotonic clock")
        self._last = now
        self._seen = {key: deadline for key, deadline in self._seen.items() if deadline > now}
        key = (command.hub_id, command.id)
        if key in self._seen:
            return False
        if len(self._seen) >= self.capacity:
            raise ValueError("replay window full")
        self._seen[key] = now + MAX_TTL_S
        return True
