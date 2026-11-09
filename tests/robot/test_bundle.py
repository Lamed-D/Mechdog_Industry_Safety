import unittest
from unittest.mock import patch

from tests import fakes
from tests.fakes.fake_socket import FakeNet
from tests.fakes.fake_time import FakeClock
from tools.bundle_robot import render


class BundleTests(unittest.TestCase):
    def test_startup_error_is_preserved_when_action_stop_also_fails(self):
        fakes.install()
        try:
            with patch.dict("sys.modules", {"socket": FakeNet(), "time": FakeClock(1000)}), \
                    patch.object(fakes.Hiwonder, "startMain", side_effect=RuntimeError("registration failure")), \
                    patch.object(fakes.HW_MechDog.MechDog, "stop_action", side_effect=OSError("stop failure")):
                with self.assertRaisesRegex(RuntimeError, "registration"):
                    exec(compile(render("B"), "bundle", "exec"), {})
            self.assertEqual(fakes.HW_MechDog.instances[-1].last_move, (0, 0))
        finally:
            fakes.uninstall()

    def test_startup_registration_failure_attempts_both_stops(self):
        fakes.install()
        try:
            with patch.dict("sys.modules", {"socket": FakeNet(), "time": FakeClock(1000)}), \
                    patch.object(fakes.Hiwonder, "startMain", side_effect=RuntimeError("synthetic registration failure")):
                with self.assertRaisesRegex(RuntimeError, "registration"):
                    exec(compile(render("A"), "bundle", "exec"), {})
            dog = fakes.HW_MechDog.instances[-1]
            self.assertTrue(dog.fake_calls("stop_action"))
            self.assertEqual(dog.last_move, (0, 0))
        finally:
            fakes.uninstall()

    def test_both_ids_start_latched_with_fake_modules(self):
        for robot in ("A", "B"):
            with self.subTest(robot=robot):
                fakes.install()
                try:
                    with patch.dict("sys.modules", {"socket": FakeNet(), "time": FakeClock(1000)}):
                        scope = {}
                        exec(compile(render(robot), "bundle", "exec"), scope)
                    app = scope["_bundle_modules"]["main"].app
                    self.assertEqual(app.cfg.ROBOT_ID, robot)
                    self.assertTrue(app.robot.latched)
                    self.assertEqual(app.motion.dog.last_move, (0, 0))
                    self.assertEqual(len(fakes.Hiwonder.main_funcs), 4)
                    app.robot.handle(("CMD|ESTOP|%s|1|$" % robot).encode())
                    self.assertEqual(app.robot.latch_reason, "estop")
                finally:
                    fakes.uninstall()

    def test_output_is_deterministic_and_rejects_unknown_robot(self):
        self.assertEqual(render("A"), render("A"))
        with self.assertRaises(ValueError):
            render("C")
