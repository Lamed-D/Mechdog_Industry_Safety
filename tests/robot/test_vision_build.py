import contextlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from tools import build_vision_cam as builder


class BuildPublicationTests(unittest.TestCase):
    def test_latest_survives_failed_compile_and_replaces_only_after_success(self):
        root = builder.ROOT / "build"
        root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as directory:
            build = Path(directory)
            compile_dir, latest = build / "compile", build / "latest"
            latest.mkdir()
            (latest / "previous.bin").write_bytes(b"previous successful firmware")
            boot = build / "Arduino15/packages/esp32/hardware/esp32/test/tools/partitions/boot_app0.bin"
            boot.parent.mkdir(parents=True)
            boot.write_bytes(b"boot")

            def successful_tool(cmd, **kwargs):
                if "compile" in cmd:
                    self.assertEqual(cmd[cmd.index("--build-path") + 1], str(compile_dir))
                    self.assertTrue((latest / "previous.bin").exists())
                    compile_dir.mkdir()
                    (compile_dir / "vision_cam.ino.bin").write_bytes(b"app")
                else:
                    Path(cmd[cmd.index("-o") + 1]).write_bytes(b"merged firmware")

            with patch.multiple(builder, BUILD=build, COMPILE=compile_dir, RELEASE=latest, LOCAL=build), \
                    patch.object(builder, "find_tool", return_value=Path("fake-tool")), \
                    patch("sys.argv", ["build_vision_cam.py", "--release", "--profile", "detail"]), \
                    contextlib.redirect_stdout(io.StringIO()):
                with patch.object(builder.subprocess, "run", side_effect=subprocess.CalledProcessError(1, "compile")):
                    with self.assertRaises(subprocess.CalledProcessError):
                        builder.main()
                self.assertEqual((latest / "previous.bin").read_bytes(), b"previous successful firmware")
                with patch.object(builder.subprocess, "run", side_effect=successful_tool):
                    builder.main()
            self.assertFalse((latest / "previous.bin").exists())
            self.assertEqual(set(p.name for p in latest.iterdir()),
                             {"mechdog_vision_cam_0x0.bin", "mechdog_vision_cam_0x0.sha256", "manifest.json"})
            self.assertEqual(json.loads((latest / "manifest.json").read_text())["profile"], "detail")
