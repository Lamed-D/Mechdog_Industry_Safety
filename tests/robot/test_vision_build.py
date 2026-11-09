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
                    (compile_dir / "build.options.json").write_text(json.dumps({
                        "hardwareFolders": "/packages/esp32/hardware/esp32/3.3.12"}), encoding="utf-8")
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
            manifest = json.loads((latest / "manifest.json").read_text())
            self.assertEqual(manifest["core_version"], "3.3.12")
            self.assertEqual(manifest["source_sha256"], builder.source_manifest()["source_sha256"])
            self.assertIn("firmware/vision_cam/config.h", manifest["source_files"])
            with patch.object(builder, "RELEASE", latest):
                self.assertEqual(builder.verify_release()["profile"], "detail")
                with patch.object(builder, "source_manifest", return_value={"source_sha256": "changed"}):
                    with self.assertRaises(ValueError):
                        builder.verify_release()
                checksum = latest / "mechdog_vision_cam_0x0.sha256"
                original_checksum = checksum.read_text()
                checksum.write_text("incorrect")
                with self.assertRaises(ValueError):
                    builder.verify_release()
                checksum.write_text(original_checksum)
                (latest / "mechdog_vision_cam_0x0.bin").write_bytes(b"changed")
                with self.assertRaises(ValueError):
                    builder.verify_release()

    def test_source_manifest_is_repeatable_and_never_contains_absolute_paths(self):
        manifest = builder.source_manifest()
        self.assertEqual(manifest, builder.source_manifest())
        self.assertTrue(all(not Path(name).is_absolute() for name in manifest["source_files"]))
        self.assertNotIn("secrets.h", [Path(name).name for name in manifest["source_files"]])

    def test_source_change_during_compile_preserves_previous_release(self):
        root = builder.ROOT / "build"
        with tempfile.TemporaryDirectory(dir=root) as directory:
            build = Path(directory)
            latest = build / "latest"
            latest.mkdir()
            (latest / "previous.bin").write_bytes(b"keep")
            compile_dir = build / "compile"
            compile_dir.mkdir()
            (compile_dir / "vision_cam.ino.bin").write_bytes(b"app")
            with patch.multiple(builder, BUILD=build, COMPILE=compile_dir, RELEASE=latest), \
                    patch.object(builder, "find_tool", return_value=Path("fake-tool")), \
                    patch.object(builder, "compiled_core_version", return_value="3.3.12"), \
                    patch.object(builder, "source_manifest", side_effect=[{"source_sha256": "before"}, {"source_sha256": "after"}]), \
                    patch.object(builder.subprocess, "run"), \
                    patch("sys.argv", ["build_vision_cam.py", "--release"]), contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit):
                    builder.main()
            self.assertEqual((latest / "previous.bin").read_bytes(), b"keep")

    def test_core_version_must_match_required_version(self):
        with tempfile.TemporaryDirectory(dir=builder.ROOT / "build") as directory:
            folder = Path(directory)
            with patch.object(builder, "COMPILE", folder):
                for versions in ("", "/packages/esp32/hardware/esp32/3.3.11",
                                 "/packages/esp32/hardware/esp32/3.3.12,/packages/esp32/hardware/esp32/3.3.11"):
                    (folder / "build.options.json").write_text(json.dumps({"hardwareFolders": versions}))
                    with self.subTest(versions=versions), self.assertRaises(SystemExit):
                        builder.compiled_core_version()
