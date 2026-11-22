"""메인 ESP32 Arduino 펌웨어를 컴파일만 합니다(업로드·합본·굽기 없음).

벤더 라이브러리(HW_MechDog 등)는 저장소에 없습니다. 제조사 ESP32 개발 패키지로 Arduino 에 설치한 뒤,
그 라이브러리 폴더를 환경변수 MECHDOG_VENDOR_LIBS 로 알려 주면 컴파일합니다(없으면 Arduino 기본 사용자
라이브러리에서 찾습니다). 굽기는 사용자만, Arduino IDE 에서 합니다(ai/firmware.md 4.2절).

실행: python firmware/builder/build_main_arduino.py            # build/main_arduino/compile
      python firmware/builder/build_main_arduino.py --robot A  # build/robot_A/arduino, secrets.h 의 ID 가 A 인지 확인
  (선택) set MECHDOG_VENDOR_LIBS=C:\\Users\\<you>\\Documents\\Arduino\\libraries
  (선택) set ARDUINO_CLI=C:\\Program Files\\Arduino IDE\\resources\\app\\lib\\backend\\resources\\arduino-cli.exe
"""
import argparse
import os
from pathlib import Path
import re
import subprocess
import sys

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


def secrets_robot_id():
    """secrets.h 의 MECH_ROBOT_ID('A'/'B'). 파일이 없으면 None(예시 값으로 컴파일만 됨)."""
    path = ROOT / "firmware/robot/arduino/secrets.h"
    if not path.exists():
        return None
    match = re.search(r"#define\s+MECH_ROBOT_ID\s+'([AB])'", path.read_text(encoding="utf-8"))
    return match.group(1) if match else "?"


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--robot", type=str.upper, choices=("A", "B"))
    args = parser.parse_args(argv)
    local = Path(os.environ["LOCALAPPDATA"])
    cli = find_cli()
    build = ROOT / "build/main_arduino/compile"
    if args.robot:
        # Arduino 판은 사용자가 Arduino IDE 로 올리고 ID 는 Wi-Fi 값과 같은 secrets.h 에서 옵니다.
        # 그래서 빌드에서 ID 를 바꾸지 않고, secrets.h 가 요청한 ID 와 같은지만 확인합니다.
        found = secrets_robot_id()
        if found is None:
            print("주의: secrets.h 가 없어 예시 값(ID A, 가짜 Wi-Fi)으로 컴파일만 합니다. 업로드 전 secrets.h 를 만드세요.")
        elif found != args.robot:
            sys.exit("secrets.h 의 MECH_ROBOT_ID 가 %s 입니다. 로봇 %s 용이면 '%s' 로 고친 뒤 다시 실행하세요."
                     % (found, args.robot, args.robot))
        build = ROOT / "build" / ("robot_" + args.robot) / "arduino"
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
    return build


if __name__ == "__main__":
    main()
