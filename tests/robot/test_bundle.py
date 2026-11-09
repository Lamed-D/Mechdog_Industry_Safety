import unittest
from unittest.mock import patch

from tests import fakes
from tests.fakes.fake_socket import FakeNet
from tests.fakes.fake_time import FakeClock
from tools.bundle_robot import render


class BundleTests(unittest.TestCase):
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
