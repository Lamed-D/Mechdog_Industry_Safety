"""firmware/main_arduino 이식성 코어(안전 로직)의 행위 테스트를 돌립니다.

tests/firmware/test_core.cpp 를 호스트 C++ 컴파일러로 빌드·실행합니다. 컴파일러가 없으면
로컬에 받아 둔 gcc Docker 이미지로 대신 돌립니다. 둘 다 없으면 건너뜁니다(게이트를 깨지 않음).
벤더·Arduino 없이 표준 C++ 로 도는 코어만 검사합니다(벤더 글루는 Arduino IDE 컴파일로 확인).

실행: python tools/test_main_arduino.py
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = "tests/firmware/test_core.cpp"
INC = "firmware/main_arduino"
DOCKER_IMAGE = os.environ.get("MECHDOG_TEST_DOCKER", "gcc:14-bookworm")


def run_host():
    for cc in ("g++", "c++", "clang++"):
        if shutil.which(cc):
            exe = ROOT / "build" / "test_core.exe"
            exe.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run([cc, "-std=c++17", "-Wall", "-I", INC, SRC, "-o", str(exe)],
                           cwd=ROOT, check=True)
            return subprocess.run([str(exe)], cwd=ROOT).returncode
    return None


def run_docker():
    if not shutil.which("docker"):
        return None
    has = subprocess.run(["docker", "image", "inspect", DOCKER_IMAGE],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if has.returncode != 0:
        return None  # 이미지를 자동으로 내려받지 않음(큰 다운로드 방지)
    cmd = ["docker", "run", "--rm", "-v", "%s:/work" % ROOT, "-w", "/work", DOCKER_IMAGE,
           "bash", "-c", "g++ -std=c++17 -Wall -I %s %s -o /tmp/tc && /tmp/tc" % (INC, SRC)]
    return subprocess.run(cmd).returncode


def main():
    code = run_host()
    if code is None:
        code = run_docker()
    if code is None:
        print("건너뜀: C++ 컴파일러도 gcc Docker 이미지도 없음. "
              "Arduino IDE 컴파일로 확인하세요(firmware/main_arduino/README.md).")
        return 0
    return code


if __name__ == "__main__":
    sys.exit(main())
