import tempfile
from pathlib import Path
import unittest
from tools.package_robot_checks import ROOT, SCRIPTS, package, verify


class HandoffPackageTests(unittest.TestCase):
    def test_exact_test_only_files_and_tamper_detection(self):
        (ROOT / "build").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / "build") as directory:
            folder = Path(directory)
            package(folder)
            self.assertTrue(verify(folder))
            self.assertEqual({p.name for p in folder.glob("*.py")}, set(SCRIPTS))
            self.assertNotIn("main.py", SCRIPTS)
            (folder / "robot_motion_check.py").write_bytes(b"changed")
            with self.assertRaises(ValueError):
                verify(folder)

    def test_unknown_main_is_not_deleted_or_packaged(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "build") as directory:
            folder = Path(directory)
            (folder / "main.py").write_bytes(b"keep")
            with self.assertRaises(ValueError):
                package(folder)
            self.assertEqual((folder / "main.py").read_bytes(), b"keep")

    def test_zero_face_box_is_no_result_and_invalid_shape_unknown(self):
        from tests import fakes
        from tests.fakes.fake_time import FakeClock
        from tests.robot.test_bringup import load
        import contextlib
        import io
        fakes.install()
        self.addCleanup(fakes.uninstall)
        probe = load("vision_probe")
        with contextlib.redirect_stdout(io.StringIO()):
            for value, expected in (([0, 0, 0, 0], False), ([40, 30, 20, 20], True), ([0, 0], False)):
                fakes.Hiwonder_IIC.fake_set_face(value)
                self.assertEqual(probe.run(fakes.Hiwonder_IIC, FakeClock())["has_result"], expected)
            fakes.Hiwonder_IIC.fake_set_face(["invalid"])
            self.assertEqual(probe.run(fakes.Hiwonder_IIC, FakeClock())["status"], "unknown")
