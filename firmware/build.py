"""로봇 A/B 펌웨어를 한 번에 빌드합니다. 사람과 AI 가 같은 명령을 씁니다 (장치에는 쓰지 않음).

    python firmware/build.py A                       # 로봇 A: 본체 Python 파일 + 카메라 합본
    python firmware/build.py B --only python         # 본체 Python 파일만
    python firmware/build.py A --only vision --profile detail
    python firmware/build.py A --only arduino        # 본체 Arduino 판(예비) 컴파일 확인

결과는 build/robot_<ID>/ 아래에 모입니다.
    python/          본체에 올릴 .py 파일 (사람이 Hiwonder Python Editor 로 업로드)
    vision/latest/   카메라 합본 mechdog_vision_cam_0x0.bin (AI 에이전트가 굽기)
    arduino/         Arduino 판 컴파일 결과 (사람이 Arduino IDE 로 업로드, ID 는 secrets.h)
"""
import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "builder"))

import build_main_arduino  # noqa: E402
import build_vision_cam  # noqa: E402
import make_robot_files  # noqa: E402

TARGETS = ("python", "vision", "arduino")
NEXT = {
    "python": "사람: 가이드 ai/firmware.md 2.2절 순서로 업로드 (secrets.py 는 따로)",
    "vision": "AI 에이전트: ai/firmware.md 6.5절로 굽기. 0x0 합본을 구우면 카메라 ID 가 이 로봇 ID 로 시작",
    "arduino": "사람: ai/firmware.md 4.2절로 Arduino IDE 업로드 (secrets.h 의 MECH_ROBOT_ID 가 이 ID 인지 확인됨)",
}


def run(target, robot, profile, arduino_cli=None):
    if target == "python":
        return make_robot_files.main([robot])
    tool_args = ["--arduino-cli", arduino_cli] if arduino_cli else []
    if target == "vision":
        return build_vision_cam.main(["--release", "--robot", robot, "--profile", profile, *tool_args])
    return build_main_arduino.main(["--robot", robot, *tool_args])


def main():
    parser = argparse.ArgumentParser(description="로봇 A/B 펌웨어 빌드 (build/robot_<ID>/)")
    parser.add_argument("robot", type=str.upper, choices=("A", "B"), help="로봇 ID")
    parser.add_argument("--only", nargs="+", choices=TARGETS, default=["python", "vision"],
                        help="빌드할 대상 (기본: python vision)")
    parser.add_argument("--profile", choices=("balanced", "detail"), default="balanced", help="카메라 영상 프로필")
    parser.add_argument("--arduino-cli", help="Vision/Arduino 빌드에 사용할 Arduino CLI 실행 파일 경로")
    args = parser.parse_args()

    results = []
    for target in args.only:
        print("\n=== %s (로봇 %s) ===" % (target, args.robot))
        try:
            out = run(target, args.robot, args.profile, args.arduino_cli)
            results.append((target, True, out))
        except subprocess.CalledProcessError:
            hint = " — 제조사 MechDog 라이브러리 설치·MECHDOG_VENDOR_LIBS 확인" if target == "arduino" else ""
            results.append((target, False, "컴파일 실패(위 로그 참고)" + hint))
        except (SystemExit, OSError, ValueError) as error:
            results.append((target, False, error))

    print("\n=== 결과: 로봇 %s ===" % args.robot)
    for target, ok, detail in results:
        if ok:
            print("[성공] %-8s %s\n         다음: %s" % (target, detail, NEXT[target]))
        else:
            print("[실패] %-8s %s" % (target, detail))
    if not all(ok for _, ok, _ in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
