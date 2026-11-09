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

    def test_read_face_error_is_not_hidden_by_legacy_retry(self):
        camera = Vision(fakes.Hiwonder_IIC)
        fakes.Hiwonder_IIC.fake_set_face(OSError(19))
        result = camera.read_face()
        self.assertEqual(result["status"], "unknown")
        self.assertIn(("read_face", ()), fakes.Hiwonder_IIC.calls)
        self.assertNotIn(("face_recognition", ()), fakes.Hiwonder_IIC.calls)

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


class VisionResultShapeTests(unittest.TestCase):
    """docs/protocol.md 11절: 맞춤 카메라 펌웨어의 '결과 없음'을 결과로 오인하지 않습니다."""

    def setUp(self):
        fakes.install()
        self.addCleanup(fakes.uninstall)

    def read(self, value, **kwargs):
        camera = Vision(fakes.Hiwonder_IIC, **kwargs)
        fakes.Hiwonder_IIC.fake_set_face(value)
        return camera.read_face()

    def test_empty_box_and_center_are_no_result(self):
        for value in ([0, 0, 0, 0], (0, 0), False, 0):
            result = self.read(value)
            self.assertEqual(result["status"], "observed")
            self.assertFalse(result["has_result"], value)

    def test_box_with_width_is_result_but_never_fall(self):
        result = self.read([40, 30, 25, 25])
        self.assertTrue(result["has_result"])
        self.assertEqual(result["fallen_person"], "unknown")

    def test_recognition_location_is_reported(self):
        self.assertEqual(self.read([0, 0, 0, 0])["recognition"], "off_on_camera")
        self.assertEqual(self.read(True, recognition_on_camera=True)["recognition"], "on_camera")
        self.assertEqual(self.read([0, 0, 0, 0])["camera_link"], "ok")

    def test_valid_legacy_and_current_shapes_keep_their_meaning(self):
        for value in (True, 1, [40, 30], (40, 30, 25, 25)):
            with self.subTest(value=value):
                result = self.read(value)
                self.assertEqual(result["status"], "observed")
                self.assertTrue(result["has_result"])
                self.assertEqual(result["fallen_person"], "unknown")

    def test_malformed_result_never_escapes_or_claims_observation(self):
        for value in ([], [1], [1, 2, 3], [1, 2, 3, 4, 5], [0, 0, "bad", 0],
                      [None, 0], [True, 0], [-1, 0], -1, [float("nan"), 0],
                      [float("inf"), 0], [[1], 0], [0, {}]):
            with self.subTest(value=value):
                self.assertEqual(self.read(value)["status"], "unknown")
