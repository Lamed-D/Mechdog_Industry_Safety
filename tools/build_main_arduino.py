"""메인 ESP32 예비 판 골격 컴파일만 수행합니다. 업로드·합본 배포 기능 없음."""
import os
from pathlib import Path
import subprocess

try:
    from .arduino_workspace import configuration
except ImportError:
    from arduino_workspace import configuration

ROOT = Path(__file__).resolve().parents[1]


def main():
    local = Path(os.environ["LOCALAPPDATA"])
    cli = Path(os.environ.get("ARDUINO_CLI", local / "Programs/Arduino IDE/resources/app/lib/backend/resources/arduino-cli.exe"))
    build = ROOT / "build/main_arduino/compile"
    if not build.resolve().is_relative_to(ROOT.resolve()):
        raise ValueError("build outside workspace")
    config, env = configuration()
    remap = "-fmacro-prefix-map=%s=/arduino15 -fmacro-prefix-map=%s=/src" % (local / "Arduino15", ROOT)
    subprocess.run([str(cli), "--config-file", str(config), "compile", "--fqbn", "esp32:esp32:esp32",
        "--build-path", str(build), "--warnings", "all", "--build-property", "compiler.cpp.extra_flags=" + remap,
        str(ROOT / "firmware/main_arduino")], check=True, env=env)
    print("compile-only skeleton:", (build / "main_arduino.ino.bin").stat().st_size, "bytes; not deployable")


if __name__ == "__main__":
    main()
