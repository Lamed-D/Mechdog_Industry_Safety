# 부품 조립과 반복 루프. 하드웨어 모듈은 main.py 가 넘겨 줍니다.
# 스레드는 감시 하나만 Hiwonder.startMain 으로 만들고(Wi-Fi 보다 먼저), 명령·텔레메트리·라이다 중계·비전 읽기는
# main.py 의 시작 스레드에서 run() 한 루프로 차례로 돕니다. 실물(2026-11-22)에서 순정 펌웨어 + Wi-Fi 뒤에는
# 시스템 메모리(free heap 52 bytes)가 모자라 두 번째 스레드부터 "can't create thread" 였기 때문입니다.
# 감시가 수신과 다른 스레드라 수신 루프가 멈춰도 600 ms 뒤 정지합니다(ai/protocol.md 5.1절).

from comm import Link
from core import Robot
from motion import Motion

COMM_PERIOD_MS = 5
VISION_PERIOD_MS = 200


def make_lock():
    """동시 상태 변경을 직렬화합니다. 잠금을 만들 수 없으면 시작하지 않습니다."""
    try:
        import _thread
        return _thread.allocate_lock()
    except Exception as error:
        raise RuntimeError("safety lock unavailable") from error


def safe_reader(func):
    """읽기 함수가 None·예외를 내면 예외로 바꿔, core 가 '모름(NA)'으로 처리하게 합니다."""
    def read():
        value = func()
        if value is None:
            raise ValueError("no value")
        return value
    return read


class App:
    def __init__(self, cfg, dog, read_battery, read_tilt, network, socket, machine, clock,
                 ssid=None, password=None, lock=None, vision=None):
        self.cfg = cfg
        self.clock = clock
        self.motion = Motion(dog)
        self.lock = lock if lock is not None else make_lock()
        self.robot = Robot(cfg, self.motion, clock, read_battery, safe_reader(read_tilt), self.lock)
        self.link = Link(cfg, network, socket, clock, ssid, password)
        self.lidar = None  # 라이다 J5 중계(동결)는 LIDAR_RELAY_ENABLED 일 때만: UART 버퍼·TCP 서버가 메모리를 씀
        if getattr(cfg, "LIDAR_RELAY_ENABLED", False):
            from lidar_bridge import LidarBridge
            self.lidar = LidarBridge(cfg, machine, socket, clock)
        self.vision = vision
        self.next_vision_ms = None
        self.vision_status = {"status": "unknown", "reason": "not_read"}
        self.ready = False
        self.startup_failed = False

    def start(self, start_main):
        if self.ready or self.startup_failed:
            raise RuntimeError("startup already attempted; restart required")
        try:
            self.motion.stop()
            start_main(self.watchdog_loop)  # Wi-Fi 가 메모리를 쓰기 전에 감시 스레드부터
            self.link.start()
            self._update_conditions()
            self.ready = True
        except BaseException:
            self.startup_failed = True
            try:
                self.robot.fail_safe()
            except Exception:
                pass
            raise

    def _update_conditions(self):
        lidar = self.lidar
        conditions = (("pm_on", self.link.pm_on),
                      ("lidar_uart", lidar is not None and not lidar.uart_ok()),
                      ("lidar_backlog", lidar is not None and lidar.backlogged()))
        with self.lock:
            for word, active in conditions:
                if active:
                    self.robot.conditions.add(word)
                else:
                    self.robot.conditions.discard(word)

    # --- 한 단계 (테스트가 직접 부름) ---
    def comm_step(self):
        self.link.service()
        self._update_conditions()
        for data, addr in self.link.poll():
            self.robot.handle(data, addr)
        if self.robot.telemetry_due():
            dest = self.robot.telemetry_dest()
            line = self.robot.telemetry()
            self.link.send(line, dest)
            role = self.robot.role_status()
            if role is not None:
                self.link.send(role, dest)

    def watchdog_step(self):
        self.robot.tick(self.link.connected())

    def lidar_step(self):
        self.lidar.service(self.link.connected())

    def vision_step(self):
        # IIC(2) camera read is outside the safety lock and never issues motion.
        self.vision_status = self.vision.read_face()

    def vision_failed(self):
        self.vision_status = {"status": "unknown", "reason": "camera_read_failed"}

    def main_step(self):
        """시작 스레드 한 바퀴: 명령·텔레메트리, (켜져 있으면) 라이다 중계, 200 ms 마다 비전 읽기.
        부분마다 실패 처리를 따로 해서, 라이다·비전 문제로 로봇을 멈추지 않습니다(통신 실패만 fail_safe)."""
        try:
            self.comm_step()
        except Exception:
            self.robot.fail_safe()
        if self.lidar is not None:
            try:
                self.lidar_step()
            except Exception:
                self.lidar.stop()
        if self.vision is not None:
            now = self.clock.ticks_ms()
            if self.next_vision_ms is None or self.clock.ticks_diff(now, self.next_vision_ms) >= 0:
                self.next_vision_ms = self.clock.ticks_add(now, VISION_PERIOD_MS)
                try:
                    self.vision_step()
                except Exception:
                    self.vision_failed()

    def run(self):
        """start() 뒤 main.py 가 부릅니다. 돌아오지 않으며, 중단·예외 시 fail_safe 후 예외를 올립니다."""
        self._forever(self.main_step, COMM_PERIOD_MS, self.robot.fail_safe)

    # --- 반복 루프 ---
    def _forever(self, step, period_ms, on_error):
        try:
            while not self.startup_failed:
                try:
                    if self.ready:  # 모든 루프 등록 전에 명령 처리를 시작하지 않음
                        step()
                except Exception:
                    on_error()
                self.clock.sleep_ms(period_ms)  # 다른 루프에 차례를 넘김
        finally:
            self.robot.fail_safe()  # 동작 그룹도 정지하고 사람 RESET 전까지 래치

    def watchdog_loop(self):
        self._forever(self.watchdog_step, self.cfg.WATCHDOG_PERIOD_MS, self.robot.fail_safe)
