"""메인 ESP32 Arduino 펌웨어를 컴파일만 합니다(업로드·합본·굽기 없음).

벤더 라이브러리(HW_MechDog 등)는 저장소에 없습니다. 제조사 ESP32 개발 패키지로 Arduino 에 설치한 뒤,
그 라이브러리 폴더를 환경변수 MECHDOG_VENDOR_LIBS 로 알려 주면 컴파일합니다(없으면 Arduino 기본 사용자
라이브러리에서 찾습니다). 굽기는 사용자만, Arduino IDE 에서 합니다(ai/firmware.md 1.4절).

실행: python ai/tools/build_main_arduino.py
  (선택) set MECHDOG_VENDOR_LIBS=C:\\Users\\<you>\\Documents\\Arduino\\libraries
  (선택) set ARDUINO_CLI=C:\\Program Files\\Arduino IDE\\resources\\app\\lib\\backend\\resources\\arduino-cli.exe
"""
import os
from pathlib import Path
import subprocess

try:
    from .arduino_workspace import configuration
except ImportError:
    from arduino_workspace import configuration

ROOT = Path(__file__).resolve().parents[2]


def find_cli():
    env = os.environ.get("ARDUINO_CLI")
    if env:
        return Path(env)
    local = Path(os.environ["LOCALAPPDATA"])
    candidates = [
        local / "Programs/Arduino IDE/resources/app/lib/backend/resources/arduino-cli.exe",
        Path(os.environ.get("ProgramFiles", "C:/Program Files"))
        / "Arduino IDE/resources/app/lib/backend/resources/arduino-cli.exe",
    ]
    for c in candidates:
        if c.exists():
            return c
    return candidates[0]  # 없으면 첫 후보로 시도(명확한 오류 메시지용)


def main():
    local = Path(os.environ["LOCALAPPDATA"])
    cli = find_cli()
    build = ROOT / "build/main_arduino/compile"
    if not build.resolve().is_relative_to(ROOT.resolve()):
        raise ValueError("build outside workspace")
    config, env = configuration()
    remap = "-fmacro-prefix-map=%s=/arduino15 -fmacro-prefix-map=%s=/src" % (local / "Arduino15", ROOT)
    cmd = [str(cli), "--config-file", str(config), "compile", "--fqbn", "esp32:esp32:esp32",
           "--build-path", str(build), "--warnings", "all",
           "--build-property", "compiler.cpp.extra_flags=" + remap]
    vendor = os.environ.get("MECHDOG_VENDOR_LIBS")
    if vendor:
        for path in vendor.split(os.pathsep):
            if path:
                cmd += ["--libraries", path]
    cmd.append(str(ROOT / "firmware/robot/arduino"))
    subprocess.run(cmd, check=True, env=env)
    size = (build / "arduino.ino.bin").stat().st_size
    print("compile OK:", size, "bytes. 업로드는 Arduino IDE 에서 사용자만(여기서 배포하지 않음).")


if __name__ == "__main__":
    main()
