# 명령 처리·감시·래치·저전압 (docs/protocol.md 4·5·6절).
# 하드웨어는 motion(공식 API 호출), 배터리·기울기 읽기 함수, 시계로만 만집니다. 모두 주입받아 PC에서 시험합니다.

import proto

IDLE = "idle"
MOVING = "moving"
ACTION = "action"
STOPPED = "stopped"

# 텔레메트리 warn 순서 (6.1절 표 순서)
WARN_ORDER = ("clipped", "busy", "latched", "move_stale", "reset_denied", "garbage", "proto",
              "batt_low", "batt_unknown", "imu_unknown", "pm_on", "lidar_uart")
MAX_TEL_LEN = 160


class Robot:
    def __init__(self, cfg, motion, clock, read_battery, read_tilt):
        self.cfg = cfg
        self.motion = motion
        self.clock = clock
        self._read_battery = read_battery
        self._read_tilt = read_tilt
        now = clock.ticks_ms()
        # 부팅 직후에는 사람이 RESET 하기 전까지 움직이지 않음 (5.1절)
        self.latched = True
        self.latch_reason = "boot"
        self.boot_id = None
        self.last_cmd_seq = 0
        self.moving = False
        self.action_until = None      # 동작 그룹·자세 잡기가 끝나는 ticks (최대 시간)
        self.action_started = None    # 동작 그룹을 시작한 ticks (자세 잡기는 None)
        self.need_default_pose = False
        self.link_armed = False       # 첫 명령을 받은 뒤부터 통신 끊김 감시
        self.last_accept = now
        self.last_move = now
        self.wifi_ok = False
        self.battery_mv = None
        self._batt_low_since = None
        self._batt_unknown_since = now
        self._last_batt_read = None
        self.conditions = set()       # 계속되는 상태(pm_on, lidar_uart)를 밖에서 넣음
        self.events = set()           # 지난 텔레메트리 이후 생긴 일
        self.tel_addr = None
        self.tseq = 0
        self.urgent = True            # 부팅 상태를 바로 한 번 알림
        self._last_tel = now
        self.uptime_ms = 0
        self._last_tick = now

    # ---------- 공용 ----------
    def _now(self):
        return self.clock.ticks_ms()

    def _diff(self, a, b):
        return self.clock.ticks_diff(a, b)

    def busy(self):
        return self.action_until is not None and self._diff(self.action_until, self._now()) > 0

    def state(self):
        if self.latched:
            return STOPPED
        if self.busy():
            return ACTION
        if self.moving:
            return MOVING
        return IDLE

    def _stop(self):
        self.moving = False
        self.motion.stop()

    def latch(self, reason):
        """정지 + 래치. estop 은 RESET 전까지 다른 사유로 덮지 않음 (5.2절)."""
        try:
            if self.action_started is not None:
                try:
                    self.motion.stop_action()  # 동작 그룹도 멈춤. 아래 move(0, 0)과 함께
                except Exception:
                    pass
            self._stop()
        finally:
            if not (self.latched and self.latch_reason == "estop" and reason != "estop"):
                if not self.latched or self.latch_reason != reason:
                    self.urgent = True
                self.latch_reason = reason
            self.latched = True

    def fail_safe(self):
        """예상 못 한 예외가 난 경로에서 부릅니다. 멈추고 통신 끊김으로 래치."""
        self.latch("link_lost")

    # ---------- 명령 수신 (4절) ----------
    def handle(self, data, addr=None):
        kind, cmd = proto.parse(data, self.cfg.ROBOT_ID)
        if kind == proto.GARBAGE:
            self.events.add("garbage")
            return
        if kind == proto.OTHER:
            return
        if kind == proto.BAD:
            self.latch("bad_cmd")
            return
        name = cmd.name
        if name == "ESTOP":
            self._accept_if_newer(cmd.seq)
            self.latch("estop")
            return
        if name == "STOP":
            self._accept_if_newer(cmd.seq)
            self._stop()
            return
        if name == "HELLO":
            self._hello(cmd, addr)
            return
        if self.boot_id is None:
            return  # boot_id 를 모르면 STOP·ESTOP 만 (2.2절)
        if cmd.seq <= self.last_cmd_seq:
            return  # 늦게 온 옛 명령. 감시 타이머도 갱신하지 않음
        self._accept(cmd.seq)
        if self.latched:
            if name == "RESET":
                self._reset()
            elif name in ("MOVE", "ACTION", "POSE"):
                self.events.add("latched")
            return
        if name in ("RESET", "PING"):
            return
        if self.busy():
            self.events.add("busy")
            return
        if name == "MOVE":
            self._move(cmd.args[0], cmd.args[1])
        elif name == "ACTION":
            self._action(cmd.args[0])
        elif name == "POSE":
            self._pose(cmd.args[0])

    def _accept(self, seq):
        self.last_cmd_seq = seq
        self.last_accept = self._now()
        self.link_armed = True

    def _accept_if_newer(self, seq):
        # 늦게 온 STOP·ESTOP 도 실행하지만 last_cmd_seq 를 낮추지는 않음 (4.3절)
        if self.boot_id is not None and seq > self.last_cmd_seq:
            self._accept(seq)

    def _hello(self, cmd, addr):
        if cmd.args[0] != proto.PROTO_VERSION:
            self.events.add("proto")
            return
        if addr is not None:
            self.tel_addr = addr[0]
        if cmd.seq != self.boot_id:
            self._stop()
            self.last_cmd_seq = 0
            self.boot_id = cmd.seq  # 래치는 그대로 둠
            self.urgent = True
        self.last_accept = self._now()
        self.link_armed = True

    def _reset(self):
        ok = (self.wifi_ok and self.battery_mv is not None
              and self.battery_mv >= self.cfg.LOW_BATT_RESET_MV and not self.busy())
        if not ok:
            self.events.add("reset_denied")
            return
        self.latched = False
        self.latch_reason = "none"
        self.urgent = True

    def _move(self, step, angle):
        step, cut1 = proto.clip(step, -100, 100)
        angle, cut2 = proto.clip(angle, -30, 30)
        if cut1 or cut2:
            self.events.add("clipped")
        if step == 0 and angle == 0:
            self._stop()
            return
        if self.need_default_pose:
            # 동작 그룹 뒤 첫 MOVE: 기본 자세를 먼저 잡고, 자세가 잡힌 뒤 오는 MOVE 부터 걷기 (3.3절)
            self.need_default_pose = False
            self.motion.default_pose()
            self.action_until = self.clock.ticks_add(self._now(), self.cfg.DEFAULT_POSE_SETTLE_MS)
            self.events.add("busy")
            return
        self.motion.move(step, angle)
        self.moving = True
        self.last_move = self._now()

    def _action(self, name):
        if self.moving:
            self._stop()
        self.motion.action(name)
        duration = self.cfg.ACTION_DURATION_MS[name]
        self.action_started = self._now()
        self.action_until = self.clock.ticks_add(self.action_started, duration)
        self.need_default_pose = True

    def _pose(self, pose):
        name = proto.POSE_ACTION[pose]
        if name is not None:
            self._action(name)
            return
        self._stop()
        self.motion.default_pose()
        self.need_default_pose = False
        self.action_until = self.clock.ticks_add(self._now(), self.cfg.DEFAULT_POSE_SETTLE_MS)

    # ---------- 감시 (5절) : 수신과 다른 스레드에서 짧은 주기로 ----------
    def tick(self, wifi_connected):
        now = self._now()
        self.uptime_ms += max(self._diff(now, self._last_tick), 0)
        self._last_tick = now
        self._check_action(now)
        if not wifi_connected and self.wifi_ok:
            self.latch("link_lost")
        self.wifi_ok = wifi_connected
        if self.link_armed and self._diff(now, self.last_accept) > self.cfg.LINK_TIMEOUT_MS:
            self.link_armed = False
            self.latch("link_lost")
        if self.moving and self._diff(now, self.last_move) > self.cfg.MOVE_HOLD_MS:
            self._stop()
            self.events.add("move_stale")
        if self._last_batt_read is None or \
                self._diff(now, self._last_batt_read) >= self.cfg.BATT_READ_PERIOD_MS:
            self._last_batt_read = now
            self._check_battery(now)

    def _check_action(self, now):
        if self.action_until is None:
            return
        done = self._diff(now, self.action_until) >= 0
        if not done and self.action_started is not None and                 self._diff(now, self.action_started) >= self.cfg.ACTION_MIN_MS:
            try:
                done = bool(self.motion.action_over())  # 제조사 예제의 끝남 확인
            except Exception:
                done = False  # 모르면 최대 시간까지 기다림
        if done:
            self.action_until = None
            self.action_started = None

    def _check_battery(self, now):
        try:
            value = self._read_battery()
        except Exception:
            value = None
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            value = None  # 모르는 값을 "충분함"으로 보지 않음
        self.battery_mv = value
        cfg = self.cfg
        if value is None:
            self._batt_low_since = None
            if self._batt_unknown_since is None:
                self._batt_unknown_since = now
            if self._diff(now, self._batt_unknown_since) >= cfg.BATT_UNKNOWN_HOLD_MS:
                self.latch("low_battery")
            return
        self._batt_unknown_since = None
        if value < cfg.LOW_BATT_LATCH_MV:
            if self._batt_low_since is None:
                self._batt_low_since = now
            if self._diff(now, self._batt_low_since) >= cfg.LOW_BATT_HOLD_MS:
                self.latch("low_battery")
        else:
            self._batt_low_since = None

    # ---------- 텔레메트리 (6절) ----------
    def telemetry_due(self):
        return self.urgent or self._diff(self._now(), self._last_tel) >= self.cfg.TEL_PERIOD_MS

    def telemetry_dest(self):
        host = self.cfg.PI_HOST or self.tel_addr
        if host is None:
            return None
        return (host, self.cfg.TEL_PORT)

    def _tilt(self, words):
        try:
            angle = self._read_tilt()
            return "%.1f" % angle[0], "%.1f" % angle[1]
        except Exception:
            words.add("imu_unknown")
            return "NA", "NA"

    def telemetry(self):
        """다음 텔레메트리 한 줄. 부르면 tseq 가 오르고 이벤트 warn 이 비워집니다."""
        words = set(self.events) | self.conditions
        if self.battery_mv is None:
            words.add("batt_unknown")
            battery = "NA"
        else:
            battery = str(self.battery_mv)
            if self.battery_mv < self.cfg.LOW_BATT_WARN_MV:
                words.add("batt_low")
        tilt_x, tilt_y = self._tilt(words)
        ordered = [w for w in WARN_ORDER if w in words]
        head = "TEL|%s|%d|%d|%s|%d|%s|%s|%s|%s|%d|%s|" % (
            self.cfg.ROBOT_ID, self.tseq, self.last_cmd_seq, self.state(), 1 if self.latched else 0,
            self.latch_reason, battery, tilt_x, tilt_y, self.uptime_ms,
            self.boot_id if self.boot_id is not None else "-")
        while ordered and len(head) + len(",".join(ordered)) + 2 > MAX_TEL_LEN:
            ordered.pop()  # 길이 제한: 뒤쪽(덜 급한) 낱말부터 뺌
        line = head + (",".join(ordered) if ordered else "none") + "|$"
        self.tseq += 1
        self.events.clear()
        self.urgent = False
        self._last_tel = self._now()
        return line
