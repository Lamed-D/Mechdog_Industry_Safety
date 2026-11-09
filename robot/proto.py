# 명령 메시지 해석 (docs/protocol.md 2·3·4.4절). 하드웨어를 만지지 않는 순수 함수만 둡니다.
# MicroPython 에서도 돌도록 표준 내장 기능만 씁니다.

MAX_CMD_LEN = 64
MAX_SEQ = 2147483647
PROTO_VERSION = 0
MAX_TEL_LEN = 160
MAX_ROLE_STATUS_LEN = 96
ROLE_MIN_LEASE_MS = 100
ROLE_MAX_LEASE_MS = 1000
ROLE_PRIMARY, ROLE_SECONDARY, ROLE_NONE = "P", "S", "N"
WARN_ORDER = ("clipped", "busy", "latched", "move_stale", "reset_denied", "garbage", "proto",
              "batt_low", "batt_unknown", "imu_unknown", "pm_on", "lidar_uart", "lidar_backlog")

ACTION_ALLOW = ("stand_four_legs", "normal_attitude", "sit_dowm",
                "go_prone", "nodding_motion", "scrape_a_bow")
POSE_ACTION = {"default": None, "sit": "sit_dowm", "prone": "go_prone"}

# 이름 -> (seq 뒤) 인자 개수
_ARG_COUNT = {
    "MOVE": 2, "STOP": 0, "ACTION": 1, "POSE": 1,
    "ESTOP": 0, "RESET": 0, "PING": 0, "HELLO": 1,
    "ROLE": 4,
}
_ALL_ROBOTS_OK = ("STOP", "ESTOP")

# parse() 결과 종류
GARBAGE = "garbage"   # 누구 것인지 모름 -> 버리고 warn=garbage
OTHER = "other"       # 다른 로봇 것 -> 조용히 버림
BAD = "bad"           # 내 것인데 잘못됨 -> 정지 + 래치 bad_cmd
OK = "ok"


class Command:
    def __init__(self, name, seq, args, to_all):
        self.name = name
        self.seq = seq        # HELLO 는 boot_id 문자열
        self.args = args
        self.to_all = to_all


def parse_int(text):
    """10진 정수. 부호 '-'만 허용, '+'·소수점·공백·빈 값은 None."""
    if not text:
        return None
    digits = text[1:] if text[0] == "-" else text
    if not digits:
        return None
    for ch in digits:
        if ch not in "0123456789":
            return None
    return int(text)


def _is_boot_id(text):
    if not 1 <= len(text) <= 16:
        return False
    for ch in text:
        if not ("0" <= ch <= "9" or "a" <= ch <= "z" or "A" <= ch <= "Z"):
            return False
    return True


def _slice(data):
    start = data.find(b"CMD")
    if start < 0:
        return None
    end = data.find(b"$", start)
    if end < 0:
        return None
    return data[start:end + 1]


def parse(data, robot_id):
    """(종류, Command 또는 None). 종류는 GARBAGE/OTHER/BAD/OK."""
    if not data:
        return GARBAGE, None
    raw = _slice(bytes(data))
    if raw is None:
        return GARBAGE, None
    parts = raw.split(b"|")
    if len(parts) < 4 or parts[-1] != b"$":
        return GARBAGE, None
    try:
        target = parts[2].decode()
    except Exception:
        return GARBAGE, None
    if target != robot_id and target != "*":
        return OTHER, None
    # 여기부터는 내 것(또는 전체) -> 문제가 있으면 BAD
    if len(raw) > MAX_CMD_LEN:
        return BAD, None
    for byte in raw:
        if byte >= 128 or byte <= 32:
            return BAD, None
    fields = [p.decode() for p in parts[1:-1]]
    name = fields[0]
    count = _ARG_COUNT.get(name)
    if count is None or len(fields) != 3 + count:
        return BAD, None
    to_all = target == "*"
    if to_all and name not in _ALL_ROBOTS_OK:
        return BAD, None
    args = fields[3:]
    if name == "HELLO":
        proto = parse_int(args[0])
        if not _is_boot_id(fields[2]) or proto is None:
            return BAD, None
        return OK, Command(name, fields[2], [proto], to_all)
    seq = parse_int(fields[2])
    if seq is None or not 0 <= seq <= MAX_SEQ:
        return BAD, None
    if name == "MOVE":
        step = parse_int(args[0])
        angle = parse_int(args[1])
        if step is None or angle is None:
            return BAD, None
        args = [step, angle]
    elif name == "ACTION" and args[0] not in ACTION_ALLOW:
        return BAD, None
    elif name == "POSE" and args[0] not in POSE_ACTION:
        return BAD, None
    elif name == "ROLE":
        session, term, code, lease = args
        term, lease = parse_int(term), parse_int(lease)
        if (not _is_boot_id(session) or term is None or not 1 <= term <= MAX_SEQ
                or code not in (ROLE_PRIMARY, ROLE_SECONDARY, ROLE_NONE)
                or lease is None or not ROLE_MIN_LEASE_MS <= lease <= ROLE_MAX_LEASE_MS):
            return BAD, None
        args = [session, term, code, lease]
    return OK, Command(name, seq, args, to_all)


def clip(value, low, high):
    if value < low:
        return low, True
    if value > high:
        return high, True
    return value, False
