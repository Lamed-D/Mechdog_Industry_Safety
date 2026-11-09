"""실물 연결용 고정 위치 점검 어댑터. 경로 계획 전에는 이동·자세 명령을 실행하지 않습니다."""
import threading

from host.robot_link import RobotLink
from host.roles import RoleCoordinator


class RobotAdapter:
    def __init__(self, hub, *, clock=None):
        self.hub = hub
        options = {} if clock is None else {"clock": clock}
        self.links = {r: RobotLink(r, hub.sender(r), **options) for r in ("A", "B")}
        self.roles = RoleCoordinator(self.links, **options)
        self.failures = 0

    def step(self, core):
        try:
            for robot, data in self.hub.receive():
                self.links[robot].observe(data)
        except Exception:
            self.failures += 1
            for link in self.links.values():
                link.estop()
        self.roles.step()
        core.update()
        for command in core.drain_commands():
            link = self.links[command.robot]
            if command.kind == "estop":
                link.estop()
            else:
                # 인계 단계에서는 동작·자세도 막습니다. 공식 API 실물 확인 전 움직이지 않습니다.
                link.stop()
                if command.kind != "stop":
                    core.command_blocked(command.robot, command.kind, "stationary_mode")
        for link in self.links.values():
            try:
                link.step()
            except Exception:
                self.failures += 1
                # 한 로봇 송신 실패가 다른 로봇 ESTOP을 막지 않습니다.
                link.estop()

    def close(self):
        try:
            for link in self.links.values():
                try:
                    link.estop()
                    link.step()
                except Exception:
                    self.failures += 1
        finally:
            self.hub.close()


def start_loop(adapter, core, lock, period_s=0.1):
    stop = threading.Event()

    def run():
        try:
            while not stop.is_set():
                try:
                    with lock:
                        adapter.step(core)
                except Exception:
                    adapter.failures += 1
                    with lock:
                        core.estop_all(source="adapter_failure")
                stop.wait(period_s)
        finally:
            with lock:
                adapter.close()

    thread = threading.Thread(target=run, name="robot-adapter", daemon=True)
    thread.start()
    return stop, thread
