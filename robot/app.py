# 부품 조립과 반복 루프. 하드웨어 모듈은 main.py 가 넘겨 줍니다(PC 테스트에서는 가짜).
# 루프 셋을 Hiwonder.startMain 으로 따로 돌립니다: 명령·텔레메트리 / 감시 / 라이다 중계.
# 감시가 수신과 다른 루프라 수신이 멈춰도 600 ms 뒤 정지합니다(docs/protocol.md 5.1절).

from comm import Link
from core import Robot
from lidar_bridge import LidarBridge
from motion import Motion

COMM_PERIOD_MS = 5
LIDAR_PERIOD_MS = 2


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
        self.lidar = LidarBridge(cfg, machine, socket, clock)
        self.vision = vision
        self.vision_status = {"status": "unknown", "reason": "not_read"}
        self.ready = False
        self.startup_failed = False

    def start(self, start_main):
        if self.ready or self.startup_failed:
            raise RuntimeError("startup already attempted; restart required")
        try:
            self.motion.stop()
            self.link.start()
            self._update_conditions()
            start_main(self.watchdog_loop)
            start_main(self.comm_loop)
            start_main(self.lidar_loop)
            if self.vision is not None:
                start_main(self.vision_loop)
            self.ready = True
        except BaseException:
            self.startup_failed = True
            try:
                self.robot.fail_safe()
            except Exception:
                pass
            raise

    def _update_conditions(self):
        conditions = (("pm_on", self.link.pm_on), ("lidar_uart", not self.lidar.uart_ok()),
                      ("lidar_backlog", self.lidar.backlogged()))
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

    def vision_loop(self):
        self._forever(self.vision_step, 200, self.vision_failed)

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

    def comm_loop(self):
        self._forever(self.comm_step, COMM_PERIOD_MS, self.robot.fail_safe)

    def watchdog_loop(self):
        self._forever(self.watchdog_step, self.cfg.WATCHDOG_PERIOD_MS, self.robot.fail_safe)

    def lidar_loop(self):
        # 라이다 문제로 로봇을 멈추지 않음(7절). 연결만 정리.
        self._forever(self.lidar_step, LIDAR_PERIOD_MS, self.lidar.stop)
