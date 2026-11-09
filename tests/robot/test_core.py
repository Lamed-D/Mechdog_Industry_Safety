"""명령 처리·감시·래치·저전압·텔레메트리 (docs/protocol.md 4·5·6절)."""

import threading
import unittest

from tests import fakes
from tests.fakes.fake_time import TICKS_MAX, FakeClock
from tests.robot import _env

import core
from motion import Motion

PI = ("192.168.4.10", 50000)


class CoreTestCase(unittest.TestCase):
    start_ms = 1000

    def setUp(self):
        fakes.install()
        self.addCleanup(fakes.uninstall)
        self.cfg = _env.Cfg()
        self.clock = FakeClock(self.start_ms)
        self.dog = fakes.HW_MechDog.MechDog()
        self.imu = fakes.Hiwonder_IIC.MPU()
        self.robot = core.Robot(self.cfg, Motion(self.dog), self.clock,
                                fakes.Hiwonder.Battery_power, self.imu.read_angle)
        self.seq = 0

    # --- 도우미 ---
    def send(self, name, *args, seq=None, target="A"):
        if seq is None:
            self.seq += 1
            seq = self.seq
        fields = ["CMD", name, target, str(seq)] + [str(a) for a in args] + ["$"]
        self.robot.handle("|".join(fields).encode(), PI)

    def tick(self, ms=0, wifi=True):
        self.clock.advance(ms)
        self.robot.tick(wifi)

    def ready(self):
        """HELLO → RESET 까지 마친 정상 상태."""
        self.tick()
        self.robot.handle(b"CMD|HELLO|A|b00t|0|$", PI)
        self.send("RESET")
        self.assertFalse(self.robot.latched, self.robot.events)
        del self.dog.calls[:]  # 준비 과정(HELLO 정지)의 호출은 빼고 봄

    def wait(self, ms, step=100):
        """Pi 5 가 PING 을 계속 보내는 동안 시간이 흐름(통신 끊김 없이)."""
        for _ in range(ms // step):
            self.tick(step)
            self.send("PING")

    def moves(self):
        return self.dog.fake_calls("move")

    def tel(self):
        return self.robot.telemetry().split("|")


class BootAndHelloTest(CoreTestCase):
    def test_boot_latched_and_ignores_move(self):
        self.tick()
        self.assertEqual((self.robot.latched, self.robot.latch_reason), (True, "boot"))
        self.send("MOVE", 40, 0)
        self.assertEqual(self.moves(), [])
        fields = self.tel()
        self.assertEqual(fields[4:7], ["stopped", "1", "boot"])
        self.assertEqual(fields[11], "-")

    def test_before_hello_only_stop_and_estop(self):
        self.tick()
        self.send("RESET")
        self.assertTrue(self.robot.latched)
        self.send("STOP")
        self.assertEqual(self.moves(), [(0, 0)])
        self.send("ESTOP")
        self.assertEqual(self.robot.latch_reason, "estop")

    def test_hello_resets_seq_keeps_latch(self):
        self.ready()
        self.send("MOVE", 40, 0, seq=50)
        self.robot.handle(b"CMD|HELLO|A|new1|0|$", PI)
        self.assertEqual(self.robot.last_cmd_seq, 0)
        self.assertEqual(self.moves()[-1], (0, 0))
        self.assertTrue(self.robot.latched)  # 움직이는 중 HELLO는 이전 동작을 이어가지 않음
        self.send("RESET", seq=1)
        self.send("MOVE", 40, 0, seq=2)
        self.assertEqual(self.moves()[-1], (40, 0))
        self.robot.handle(b"CMD|HELLO|A|new1|0|$", PI)
        self.assertEqual(self.robot.last_cmd_seq, 2)
        self.assertTrue(self.robot.latched)

    def test_hello_during_action_cannot_keep_motion_alive(self):
        self.ready()
        self.send("ACTION", "nodding_motion")
        self.robot.handle(b"CMD|HELLO|A|b00t|0|$", PI)
        self.assertTrue(self.robot.latched)
        self.assertEqual(self.robot.latch_reason, "link_lost")
        self.assertEqual(self.dog.fake_calls("stop_action"), [()])
        self.assertEqual(self.moves()[-1], (0, 0))

    def test_hello_wrong_version(self):
        self.tick()
        self.robot.handle(b"CMD|HELLO|A|b00t|1|$", PI)
        self.assertIsNone(self.robot.boot_id)
        self.assertIn("proto", self.tel()[12])

    def test_reset_needs_wifi_and_battery(self):
        self.tick(wifi=False)
        self.robot.handle(b"CMD|HELLO|A|b00t|0|$", PI)
        self.send("RESET")
        self.assertTrue(self.robot.latched)
        self.assertIn("reset_denied", self.robot.events)
        fakes.Hiwonder.fake_set_battery(6700)  # LOW_BATT_RESET_MV 미만
        self.tick(300, wifi=True)
        self.send("RESET")
        self.assertTrue(self.robot.latched)
        fakes.Hiwonder.fake_set_battery(None)
        self.tick(300)
        self.send("RESET")
        self.assertTrue(self.robot.latched)
        fakes.Hiwonder.fake_set_battery(7500)
        self.tick(300)
        self.send("RESET")
        self.assertFalse(self.robot.latched)
        self.assertEqual(self.moves(), [(0, 0)])  # HELLO 때 정지뿐, 해제만으로는 움직이지 않음


class CommandTest(CoreTestCase):
    def test_move_and_clip(self):
        self.ready()
        self.send("MOVE", 150, -45)
        self.assertEqual(self.moves(), [(100, -30)])
        fields = self.tel()
        self.assertEqual(fields[4], "moving")
        self.assertIn("clipped", fields[12])
        self.assertNotIn("clipped", self.tel()[12])  # 이벤트는 한 번만

    def test_move_zero_is_stop(self):
        self.ready()
        self.send("MOVE", 40, 0)
        self.send("MOVE", 0, 0)
        self.assertEqual(self.moves(), [(40, 0), (0, 0)])
        self.assertEqual(self.robot.state(), core.IDLE)

    def test_old_seq_dropped_but_late_stop_runs(self):
        self.ready()
        self.send("MOVE", 0, 0, seq=11)
        self.send("MOVE", 60, 0, seq=10)
        self.assertEqual(self.moves(), [(0, 0)])
        self.send("MOVE", 40, 0, seq=12)
        self.send("STOP", seq=3)
        self.assertEqual(self.moves()[-1], (0, 0))
        self.assertEqual(self.robot.last_cmd_seq, 12)

    def test_bad_command_latches(self):
        self.ready()
        self.send("MOVE", 40, 0)
        self.send("ACTION", "boxing")
        self.assertEqual(self.moves()[-1], (0, 0))
        self.assertEqual(self.robot.latch_reason, "bad_cmd")
        self.assertEqual(self.dog.fake_calls("action_run"), [])

    def test_garbage_and_other_robot(self):
        self.ready()
        self.robot.handle(b"hello", PI)
        self.send("MOVE", 40, 0, target="B")
        self.assertFalse(self.robot.latched)
        self.assertEqual(self.moves(), [])
        self.assertIn("garbage", self.tel()[12])

    def test_action_busy_then_default_pose_before_move(self):
        self.ready()
        self.send("MOVE", 40, 0)
        self.send("ACTION", "nodding_motion")
        self.assertEqual(self.dog.fake_calls("action_run"), [("nodding_motion",)])
        self.assertEqual(self.moves()[-1], (0, 0))  # 걷다가 동작 전 정지
        self.assertEqual(self.robot.state(), core.ACTION)
        self.send("MOVE", 40, 0)
        self.send("POSE", "sit")
        self.assertIn("busy", self.robot.events)
        self.assertEqual(len(self.dog.fake_calls("action_run")), 1)
        self.wait(self.cfg.ACTION_DURATION_MS["nodding_motion"] + 100)
        self.send("MOVE", 40, 0)  # 기본 자세 먼저
        self.assertEqual(self.dog.fake_calls("set_default_pose"), [()])
        self.assertEqual(self.moves()[-1], (0, 0))
        self.wait(self.cfg.DEFAULT_POSE_SETTLE_MS)
        self.send("MOVE", 40, 0)
        self.assertEqual(self.moves()[-1], (40, 0))

    def test_stop_and_estop_during_action(self):
        self.ready()
        self.send("POSE", "prone")
        self.assertEqual(self.dog.fake_calls("action_run"), [("go_prone",)])
        self.send("STOP")
        self.send("ESTOP")
        self.assertEqual(self.dog.fake_calls("stop_action"), [()])  # ESTOP 은 동작 그룹도 멈춤
        self.assertEqual(self.moves()[-1], (0, 0))                 # move(0, 0)도 함께
        self.assertEqual(self.robot.latch_reason, "estop")
        self.send("RESET")  # 동작 중에는 해제 안 됨
        self.assertTrue(self.robot.latched)
        self.wait(self.cfg.ACTION_DURATION_MS["go_prone"])
        self.send("RESET")
        self.assertFalse(self.robot.latched)

    def test_action_ends_early_when_reported_over(self):
        self.ready()
        self.send("ACTION", "scrape_a_bow")
        self.dog.fake_finish_action()
        self.tick(100)
        self.assertTrue(self.robot.busy())  # ACTION_MIN_MS 전에는 믿지 않음
        self.wait(200)
        self.assertFalse(self.robot.busy())

    def test_latch_without_action_still_calls_stop_action(self):
        self.ready()
        self.send("MOVE", 40, 0)
        self.send("ESTOP")
        self.assertEqual(self.dog.fake_calls("stop_action"), [()])

    def test_pose_default(self):
        self.ready()
        self.send("POSE", "default")
        self.assertEqual(self.dog.fake_calls("set_default_pose"), [()])
        self.assertTrue(self.robot.busy())


class LatchTest(CoreTestCase):
    def test_estop_attempts_action_stop_without_tracking(self):
        self.ready()
        self.dog.action_running = "nodding_motion"
        self.send("ESTOP")
        self.assertIsNone(self.dog.action_running)
        self.assertEqual(self.moves()[-1], (0, 0))

    def test_action_start_exception_remains_tracked(self):
        self.ready()
        original = self.dog.action_run

        def starts_then_fails(name):
            original(name)
            raise OSError("started before failure")

        self.dog.action_run = starts_then_fails
        with self.assertRaises(OSError):
            self.send("ACTION", "nodding_motion")
        self.robot.fail_safe()
        self.assertIsNone(self.dog.action_running)
        self.assertTrue(self.robot.latched)
        self.assertEqual(self.moves()[-1], (0, 0))
        self.send("RESET")
        self.assertTrue(self.robot.latched)

    def test_action_stop_failure_still_attempts_move_zero(self):
        self.ready()
        self.send("ACTION", "nodding_motion")

        def broken():
            raise OSError("stop unavailable")

        self.dog.stop_action = broken
        self.send("ESTOP")
        self.assertEqual(self.moves()[-1], (0, 0))
        self.assertEqual(self.robot.latch_reason, "estop")

    def test_estop_priority_and_not_overwritten(self):
        self.ready()
        self.send("MOVE", 40, 0)
        self.send("ESTOP", target="*")
        self.assertEqual(self.moves()[-1], (0, 0))
        self.send("MOVE", 40, 0)
        self.assertEqual(self.moves()[-1], (0, 0))
        self.assertIn("latched", self.robot.events)
        self.tick(self.cfg.LINK_TIMEOUT_MS + 1)  # 끊김이 와도 estop 유지
        self.robot.handle(b"junk", PI)
        self.send("ACTION", "boxing")
        self.assertEqual(self.robot.latch_reason, "estop")

    def test_latched_telemetry_sent_urgently(self):
        self.ready()
        self.robot.telemetry()
        self.assertFalse(self.robot.telemetry_due())
        self.send("ESTOP")
        self.assertTrue(self.robot.telemetry_due())
        self.assertEqual(self.tel()[5:7], ["1", "estop"])


class WatchdogTest(CoreTestCase):
    def test_link_timeout_latches(self):
        self.ready()
        self.send("MOVE", 40, 0)
        self.tick(self.cfg.LINK_TIMEOUT_MS)
        self.assertFalse(self.robot.latched)
        self.tick(1)
        self.assertEqual(self.robot.latch_reason, "link_lost")
        self.assertEqual(self.moves()[-1], (0, 0))
        self.send("MOVE", 40, 0)  # 늦게 온 MOVE 는 실행 안 함
        self.assertEqual(self.moves()[-1], (0, 0))

    def test_ping_keeps_link_but_move_goes_stale(self):
        self.ready()
        self.send("MOVE", 40, 0)
        for _ in range(7):
            self.tick(100)
            self.send("PING")
        self.assertFalse(self.robot.latched)
        self.assertEqual(self.moves()[-1], (0, 0))
        self.assertIn("move_stale", self.robot.events)
        self.assertEqual(self.robot.state(), core.IDLE)

    def test_regular_move_keeps_walking(self):
        self.ready()
        for _ in range(20):
            self.send("MOVE", 40, 0)
            self.tick(100)
        self.assertEqual(self.robot.state(), core.MOVING)
        self.assertNotIn((0, 0), self.moves())

    def test_wifi_drop_latches(self):
        self.ready()
        self.send("MOVE", 40, 0)
        self.tick(10, wifi=False)
        self.assertEqual(self.robot.latch_reason, "link_lost")
        self.assertEqual(self.moves()[-1], (0, 0))

    def test_no_link_watch_before_first_command(self):
        self.tick(5000)
        self.assertEqual(self.robot.latch_reason, "boot")


class WrapTest(CoreTestCase):
    start_ms = TICKS_MAX - 200  # ticks 넘침을 가로지름

    def test_link_timeout_across_wrap(self):
        self.ready()
        self.send("MOVE", 40, 0)
        self.tick(500)
        self.assertFalse(self.robot.latched)
        self.tick(200)
        self.assertEqual(self.robot.latch_reason, "link_lost")
        self.assertGreaterEqual(int(self.tel()[10]), 700)


class BatteryTest(CoreTestCase):
    def test_low_battery_needs_hold_time(self):
        self.ready()
        fakes.Hiwonder.fake_set_battery(6500)
        self.wait(200)  # 처음 낮은 값을 읽음
        self.send("MOVE", 40, 0)
        self.wait(self.cfg.LOW_BATT_HOLD_MS - 200)
        self.assertFalse(self.robot.latched)
        self.wait(200)
        self.assertEqual(self.robot.latch_reason, "low_battery")
        self.assertEqual(self.moves()[-1], (0, 0))

    def test_short_dip_does_not_latch(self):
        self.ready()
        fakes.Hiwonder.fake_set_battery(6500)
        self.wait(1000)
        fakes.Hiwonder.fake_set_battery(7400)
        self.wait(200)
        fakes.Hiwonder.fake_set_battery(6500)
        self.wait(1600)
        self.assertFalse(self.robot.latched)

    def test_unknown_battery_latches_after_3s(self):
        self.ready()
        fakes.Hiwonder.fake_set_battery(OSError("adc"))
        self.wait(200)  # 처음 읽기 실패
        self.wait(self.cfg.BATT_UNKNOWN_HOLD_MS - 200)
        self.assertFalse(self.robot.latched)
        fields = self.tel()
        self.assertEqual(fields[7], "NA")
        self.assertIn("batt_unknown", fields[12])
        self.wait(200)
        self.assertEqual(self.robot.latch_reason, "low_battery")

    def test_non_integer_battery_is_unknown(self):
        self.tick()
        for value in (None, True, "7800", 0, -5):
            fakes.Hiwonder.fake_set_battery(value)
            self.tick(200)
            self.assertIsNone(self.robot.battery_mv, value)

    def test_warn_level(self):
        self.ready()
        fakes.Hiwonder.fake_set_battery(6900)
        self.tick(200)
        self.assertIn("batt_low", self.tel()[12])


class TelemetryTest(CoreTestCase):
    def test_format(self):
        self.ready()
        fakes.Hiwonder_IIC.fake_set_angle([1.24, -0.46])
        self.send("MOVE", 40, 0)
        line = self.robot.telemetry()
        self.assertTrue(line.startswith("TEL|A|"))
        self.assertTrue(line.endswith("|$"))
        fields = line.split("|")
        self.assertEqual(len(fields), 14)
        self.assertEqual(fields[3:9], [str(self.robot.last_cmd_seq), "moving", "0", "none", "7800", "1.2"])
        self.assertEqual(fields[9], "-0.5")
        self.assertEqual(fields[11], "b00t")
        self.assertEqual(self.robot.telemetry().split("|")[2], str(int(fields[2]) + 1))

    def test_imu_failure_is_na(self):
        self.tick()
        fakes.Hiwonder_IIC.fake_set_angle(None)
        fields = self.tel()
        self.assertEqual(fields[8:10], ["NA", "NA"])
        self.assertIn("imu_unknown", fields[12])

    def test_destination(self):
        self.assertIsNone(self.robot.telemetry_dest())
        self.robot.handle(b"CMD|HELLO|A|b00t|0|$", PI)
        self.assertEqual(self.robot.telemetry_dest(), (PI[0], 9101))
        self.cfg.PI_HOST = "192.168.4.2"
        self.assertEqual(self.robot.telemetry_dest(), ("192.168.4.2", 9101))

    def test_length_limit(self):
        self.tick()
        self.robot.events.update(core.WARN_ORDER)
        line = self.robot.telemetry()
        self.assertLessEqual(len(line), core.MAX_TEL_LEN)
        self.assertIn("clipped", line)


class ActionSafetyTest(CoreTestCase):
    """리뷰 [차단] 재현: 동작 그룹 끝 판단과 래치 뒤 RESET 기한."""

    def test_reset_blocked_until_max_time_even_if_stop_reports_over(self):
        self.ready()
        self.send("POSE", "prone")
        self.send("ESTOP")  # fake stop_action 은 바로 '끝남'으로 바뀜
        self.wait(self.cfg.ACTION_MIN_MS)
        self.assertTrue(self.dog.action_is_over())
        self.send("RESET")
        self.assertTrue(self.robot.latched)
        self.assertIn("reset_denied", self.robot.events)
        self.wait(self.cfg.ACTION_DURATION_MS["go_prone"])
        self.send("RESET")
        self.assertFalse(self.robot.latched)

    def test_action_not_confirmed_is_stopped_at_max_time_and_still_tracked(self):
        self.ready()
        self.dog.stop_action = lambda: None  # 멈춰도 끝났다고 보고되지 않는 경우
        self.send("ACTION", "go_prone")
        self.wait(self.cfg.ACTION_DURATION_MS["go_prone"] + 200)
        self.assertEqual(self.moves()[-1], (0, 0))
        self.assertEqual(self.robot.action_name, "go_prone")  # 시간이 지났다고 끝난 것으로 보지 않음
        self.assertTrue(self.robot.busy())
        calls = []
        self.dog.stop_action = lambda: calls.append(1)
        self.send("ESTOP")
        self.assertEqual(calls, [1])  # ESTOP 은 여전히 동작 중단을 시도
        self.assertEqual(self.moves()[-1], (0, 0))

    def test_unconfirmed_action_blocks_reset_and_new_motion_after_deadline(self):
        self.ready()
        self.dog.stop_action = lambda: None
        self.dog.action_is_over = lambda: 2
        self.send("ACTION", "go_prone")
        self.wait(self.cfg.ACTION_DURATION_MS["go_prone"] + 200)
        self.send("MOVE", 40, 0)
        self.assertEqual(self.moves()[-1], (0, 0))
        self.send("ESTOP")
        self.send("RESET")
        self.assertTrue(self.robot.latched)
        self.assertTrue(self.robot.busy())

    def test_action_is_over_failure_means_not_over(self):
        self.ready()

        def broken():
            raise AttributeError("no action_is_over")
        self.dog.action_is_over = broken
        self.send("ACTION", "nodding_motion")
        self.wait(self.cfg.ACTION_DURATION_MS["nodding_motion"] + 100)
        self.assertEqual(self.robot.action_name, "nodding_motion")
        self.assertEqual(self.dog.fake_calls("stop_action"), [()])  # 최대 시간에 멈춤 시도
        self.send("ESTOP")
        self.assertEqual(self.dog.fake_calls("stop_action"), [(), ()])

    def test_stop_action_error_still_moves_zero(self):
        self.ready()

        def broken():
            raise AttributeError("no stop_action")
        self.dog.stop_action = broken
        self.send("ACTION", "go_prone")
        self.send("ESTOP")
        self.assertEqual(self.moves()[-1], (0, 0))
        self.assertEqual(self.robot.latch_reason, "estop")


class TiltValidationTest(CoreTestCase):
    def test_non_finite_or_bad_tilt_is_na(self):
        self.tick()
        for value in ([float("nan"), 0.0], [0.0, float("inf")], [True, 0.0], [1.0], "ab", [None, 1.0]):
            fakes.Hiwonder_IIC.fake_set_angle(value)
            fields = self.tel()
            self.assertEqual(fields[8:10], ["NA", "NA"], value)
            self.assertIn("imu_unknown", fields[12], value)
        fakes.Hiwonder_IIC.fake_set_angle([1, -2.25])
        self.assertEqual(self.tel()[8:10], ["1.0", "-2.2"])


class ConcurrencyTest(CoreTestCase):
    """리뷰 [차단] 재현: 수신이 move 를 부르는 도중 감시가 래치하는 경합."""

    def setUp(self):
        super().setUp()
        self.lock = threading.Lock()
        self.robot = core.Robot(self.cfg, Motion(self.dog), self.clock,
                                fakes.Hiwonder.Battery_power, self.imu.read_angle, lock=self.lock)

    def test_motion_calls_happen_under_lock(self):
        self.ready()
        seen = []
        real_move = self.dog.move

        def move(step, angle):
            seen.append(self.lock.locked())
            real_move(step, angle)
        self.dog.move = move
        self.send("MOVE", 40, 0)
        self.tick(self.cfg.LINK_TIMEOUT_MS + 1)
        self.assertEqual(seen, [True, True])

    def test_watchdog_latch_during_move_ends_stopped(self):
        self.ready()
        real_move = self.dog.move
        watchdog = []

        def move(step, angle):
            if (step, angle) != (0, 0) and not watchdog:
                # move 직전에 통신 끊김 시간이 지나고 감시 루프가 돌기 시작함
                self.clock.advance(self.cfg.LINK_TIMEOUT_MS + 1)
                thread = threading.Thread(target=self.robot.tick, args=(True,))
                watchdog.append(thread)
                thread.start()
                thread.join(0.05)
                self.assertTrue(thread.is_alive())  # 잠금 때문에 기다림
            real_move(step, angle)
        self.dog.move = move
        self.send("MOVE", 40, 0)
        watchdog[0].join(1)
        self.assertEqual(self.robot.latch_reason, "link_lost")
        self.assertEqual(self.dog.last_move, (0, 0))
        self.assertFalse(self.robot.moving)

    def test_latched_but_moving_is_stopped_by_tick(self):
        self.ready()
        self.send("MOVE", 40, 0)
        self.robot.latched = True  # 어떤 경로로든 래치 중에 moving 이 남은 경우
        self.tick(10)
        self.assertEqual(self.dog.last_move, (0, 0))


class FailSafeTest(CoreTestCase):
    def test_fail_safe_stops(self):
        self.ready()
        self.send("MOVE", 40, 0)
        self.robot.fail_safe()
        self.assertEqual(self.moves()[-1], (0, 0))
        self.assertTrue(self.robot.latched)


if __name__ == "__main__":
    unittest.main()
