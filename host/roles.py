"""Pi가 단일 조정자로 역할을 배정합니다. 역할 ACK는 모터 구동 허가가 아닙니다."""
from dataclasses import dataclass
import re
import time
from robot import config as settings, proto as wire

CODES = {"primary": wire.ROLE_PRIMARY, "secondary": wire.ROLE_SECONDARY, "none": wire.ROLE_NONE}


@dataclass(frozen=True)
class RoleStatus:
    robot: str
    boot_id: str
    term: int
    code: str
    remaining_ms: int
    tseq: int


def parse_role_status(data):
    if len(data) > wire.MAX_ROLE_STATUS_LEN:
        raise ValueError("role status too long")
    fields = data.decode("ascii").split("|")
    if len(fields) != 8 or fields[0] != "ROLE" or fields[-1] != "$":
        raise ValueError("invalid role framing")
    _, robot, session, term, code, remaining, tseq, _ = fields
    if (robot not in ("A", "B") or not re.fullmatch(r"[a-zA-Z0-9]{1,16}", session)
            or code not in CODES.values() or not term.isascii() or not term.isdigit()
            or not remaining.isascii() or not remaining.isdigit()
            or not tseq.isascii() or not tseq.isdigit()
            or not 1 <= int(term) <= wire.MAX_SEQ or not 0 <= int(remaining) <= wire.ROLE_MAX_LEASE_MS):
        raise ValueError("invalid role fields")
    return RoleStatus(robot, session, int(term), code, int(remaining), int(tseq))


class RoleCoordinator:
    def __init__(self, links, clock=time.monotonic):
        self.links, self.clock = links, clock
        self.term = 0
        self.assignments = None
        self.primary = None

    def step(self):
        eligible = sorted(r for r, link in self.links.items() if link.fresh() and not link.emergency
                          and link.latest.battery_mv is not None and link.latest.battery_mv >= settings.LOW_BATT_WARN_MV)
        # 회복한 A가 건강한 주 B를 빼앗지 않게 현재 주 역할을 유지합니다.
        primary = self.primary if self.primary in eligible else (eligible[0] if eligible else None)
        assignments = {r: ("primary" if r == primary else "secondary" if r in eligible else "none")
                       for r in self.links}
        if assignments != self.assignments:
            self.term += 1
            self.primary, self.assignments = primary, assignments
            for robot, role in assignments.items():
                self.links[robot].assign_role(self.term, role)

    def active_primary(self):
        if self.primary is None:
            return None
        link = self.links[self.primary]
        return self.primary if link.confirmed_role() == "primary" else None
