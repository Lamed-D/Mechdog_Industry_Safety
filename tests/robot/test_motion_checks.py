import unittest
from unittest.mock import patch
from tests import fakes
from tests.fakes.fake_time import FakeClock
from tests.robot.test_bringup import load


class MotionCheckTests(unittest.TestCase):
    def setUp(self):
        fakes.install()
        self.addCleanup(fakes.uninstall)
        self.probe = load("robot_motion_check")

    def run_case(self, case, clock=None):
        return self.probe.run(case, True, fakes.Hiwonder, fakes.HW_MechDog.MechDog, clock or FakeClock())

    def test_default_is_blocked_before_constructing_robot(self):
        self.assertEqual(self.probe.run("forward")["status"], "blocked")
        self.assertEqual(fakes.HW_MechDog.instances, [])

    def test_each_bounded_motion_stops_and_requires_human_observation(self):
        for case in ("stop", "forward", "backward", "left", "right"):
            result = self.run_case(case)
            dog = fakes.HW_MechDog.instances[-1]
            self.assertEqual(result["status"], "calls_completed")
            self.assertTrue(result["observation_required"])
            self.assertEqual(dog.last_move, (0, 0))
            self.assertEqual(len(dog.fake_calls("stop_action")), 2)

    def test_battery_failure_prevents_construction_and_action_timeout_stops(self):
        fakes.Hiwonder.fake_set_battery(6500)
        self.assertEqual(self.run_case("forward")["status"], "unknown")
        self.assertEqual(fakes.HW_MechDog.instances, [])
        fakes.Hiwonder.fake_set_battery(7800)
        with patch.object(fakes.Hiwonder, "Battery_power", side_effect=[7800, 6500]):
            result = self.run_case("forward")
        self.assertEqual(result["reason"], "battery_unavailable_or_low")
        self.assertEqual(fakes.HW_MechDog.instances[-1].last_move, (0, 0))
        self.assertEqual(self.run_case("action")["status"], "unknown")
        self.assertIsNone(fakes.HW_MechDog.instances[-1].action_running)

    def test_keyboard_interrupt_and_failed_action_stop_still_try_move_zero(self):
        clock = FakeClock()
        clock.sleep_ms = lambda ms: (_ for _ in ()).throw(KeyboardInterrupt())
        with self.assertRaises(KeyboardInterrupt):
            self.run_case("forward", clock)
        self.assertEqual(fakes.HW_MechDog.instances[-1].last_move, (0, 0))
        with patch.object(fakes.HW_MechDog.MechDog, "stop_action", side_effect=OSError("synthetic")):
            result = self.run_case("forward")
        self.assertEqual(result["status"], "unknown")
        self.assertEqual(fakes.HW_MechDog.instances[-1].last_move, (0, 0))

    def test_loop_check_is_opt_in_bounded_and_never_constructs_robot(self):
        probe = load("robot_loop_check")
        self.assertEqual(probe.run()["status"], "blocked")
        clock = FakeClock()
        state = probe.run(True, fakes.Hiwonder, clock)
        for callback in fakes.Hiwonder.main_funcs:
            callback()
        self.assertEqual((state["counts"], state["done"], state["errors"]), ([50]*4, [True]*4, [None]*4))
        for callback in fakes.Hiwonder.main_funcs:
            callback()
        self.assertEqual(state["counts"], [50]*4)
        self.assertEqual(fakes.HW_MechDog.instances, [])

    def test_action_completion_and_read_only_imu_probe(self):
        clock = FakeClock()
        def sleep(ms):
            clock.advance(ms)
            if clock.now_ms >= 300:
                fakes.HW_MechDog.instances[-1].fake_finish_action()
        clock.sleep_ms = sleep
        self.assertEqual(self.run_case("action", clock)["status"], "calls_completed")
        with patch.object(fakes.HW_MechDog.MechDog, "action_is_over", return_value="done"):
            self.assertEqual(self.run_case("action")["reason"], "invalid_action_completion")
        fakes.HW_MechDog.fake_reset()
        imu = load("robot_imu_check").run(fakes.Hiwonder_IIC, FakeClock())
        self.assertEqual(imu["status"], "read")
        self.assertFalse(imu["units_verified"])
        self.assertEqual(fakes.HW_MechDog.instances, [])
        self.assertEqual(fakes.machine.uarts, [])
