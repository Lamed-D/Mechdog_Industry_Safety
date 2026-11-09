import unittest
from tests import fakes
from tests.robot import _env
from vision import Vision


class VisionTests(unittest.TestCase):
    def setUp(self):
        fakes.install()
        self.addCleanup(fakes.uninstall)

    def test_official_camera_bus_without_motion(self):
        camera = Vision(fakes.Hiwonder_IIC)
        fakes.Hiwonder_IIC.fake_set_face([1, 2])
        result = camera.read_face()
        self.assertIn(("ESP32S3Cam", (2,)), fakes.Hiwonder_IIC.calls)
        self.assertEqual(result["fallen_person"], "unknown")
        self.assertEqual(fakes.HW_MechDog.instances, [])
        self.assertEqual(fakes.machine.uarts, [])

    def test_missing_failed_and_unexpected_results_are_unknown(self):
        camera = Vision(fakes.Hiwonder_IIC)
        for result in (None, OSError("unavailable"), "bad"):
            fakes.Hiwonder_IIC.fake_set_face(result)
            self.assertEqual(camera.read_face()["status"], "unknown")

    def test_init_failure_is_unknown(self):
        class Broken:
            def IIC(self, bus):
                raise OSError("unavailable")
        self.assertEqual(Vision(Broken()).read_face()["status"], "unknown")

    def test_app_camera_read_is_independent_and_does_not_move(self):
        from app import App
        from tests.fakes.fake_socket import FakeNet
        from tests.fakes.fake_time import FakeClock
        dog = fakes.HW_MechDog.MechDog()
        app = App(_env.Cfg(), dog, lambda: 7800, lambda: [0, 0],
                  fakes.network, FakeNet(), fakes.machine, FakeClock(),
                  vision=Vision(fakes.Hiwonder_IIC))
        fakes.Hiwonder_IIC.fake_set_face(True)
        app.vision_step()
        self.assertEqual(app.vision_status["fallen_person"], "unknown")
        self.assertEqual(dog.fake_calls("move"), [])
