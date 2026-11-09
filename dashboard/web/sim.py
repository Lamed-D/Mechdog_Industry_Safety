"""화면 확인용 가짜 로봇 링크와 실행 루프. 실제 로봇·네트워크에 아무것도 보내지 않습니다.

python -m dashboard.web.run --sim 으로 씁니다. RobotLink 와 같은 모양(estop, request_reset, fresh, status,
latest, last_seen, step)이며, 부팅 래치로 시작해 사람이 래치 해제해야 준비됩니다.
"""
import math
import threading
import time
from types import SimpleNamespace


class SimLink:
    def __init__(self, robot, clock=time.monotonic, battery_mv=7800):
        self.robot = robot
        self.clock = clock
        self.battery_mv = battery_mv
        self.latched, self.reason = True, "boot"
        self.online = True
        self.latest = None
        self.last_seen = -math.inf
        self.sent = []

    def step(self):
        """RobotLink.step 처럼 한 번 보내고, 가짜 로봇의 텔레메트리를 받은 것으로 칩니다."""
        if not self.online:
            return
        self.latest = SimpleNamespace(latched=self.latched, reason=self.reason, battery_mv=self.battery_mv,
                                      warnings=frozenset(), state="stopped" if self.latched else "idle")
        self.last_seen = self.clock()

    def estop(self):
        self.latched, self.reason = True, "estop"
        self.sent.append("ESTOP")

    def request_reset(self):
        if not self.fresh() or not self.latched:
            raise ValueError("reset requires fresh latched telemetry and adequate battery")
        self.latched, self.reason = False, "none"
        self.sent.append("RESET")

    def fresh(self):
        return self.latest is not None and 0 <= self.clock() - self.last_seen < 0.4

    def status(self):
        if self.latest is None or self.clock() - self.last_seen >= 1:
            return "unknown"
        return self.latest.state


def run_loop(core, links, lock, stop_event, period_s=0.1, on_commands=None):
    """10Hz: 링크 송신 → core.update → 이동 명령 넘기기. 예외가 나도 루프는 계속하되 기록합니다."""
    while not stop_event.is_set():
        with lock:
            for link in links.values():
                try:
                    link.step()
                except Exception:
                    pass   # 링크 쪽은 다음 갱신에서 신선하지 않음 → link_lost 로 처리됨
            core.update()
            commands = core.drain_commands()
        if commands and on_commands:
            on_commands(commands)
        stop_event.wait(period_s)


def start_loop(core, links, lock, period_s=0.1, on_commands=None):
    stop_event = threading.Event()
    thread = threading.Thread(target=run_loop, args=(core, links, lock, stop_event, period_s, on_commands),
                              name="dashboard-loop", daemon=True)
    thread.start()
    return stop_event, thread
