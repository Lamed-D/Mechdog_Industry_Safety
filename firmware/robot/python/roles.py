# 같은 장비의 A/B 식별자와 별개인 임대 역할. 제어 권한·래치 해제를 만들지 않습니다.
from proto import ROLE_NONE


class RoleLease:
    def __init__(self, clock):
        self.clock = clock
        self.term = 0
        self.code = ROLE_NONE
        self.deadline = None
        self.armed = False

    def grant(self, term, code, lease_ms):
        if term < self.term or (term == self.term and self.code not in (ROLE_NONE, code)):
            return False
        self.term, self.code = term, code
        self.armed = True
        self.deadline = self.clock.ticks_add(self.clock.ticks_ms(), lease_ms) if code != ROLE_NONE else None
        return True

    def remaining(self):
        return max(0, self.clock.ticks_diff(self.deadline, self.clock.ticks_ms())) if self.deadline is not None else 0

    def expire(self):
        if self.code != ROLE_NONE and self.remaining() == 0:
            self.code, self.deadline = ROLE_NONE, None
            return True
        return False
