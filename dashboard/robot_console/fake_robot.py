"""가짜 로봇: 실제 로봇 코드(robot/core.py)를 PC에서 돌리고 MechDog 호출은 화면에 찍기만 합니다.

실행: python dashboard/robot_console/fake_robot.py   (127.0.0.1:9100 에서 명령 받음)
"""
import os
import secrets as _stdlib_secrets  # noqa: F401  robot/secrets.py 에 가려지지 않게
import socket
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "robot"))

import config  # noqa: E402
from core import Robot  # noqa: E402
from motion import Motion  # noqa: E402


class Clock:
    def ticks_ms(self):
        return int(time.monotonic() * 1000) & ((1 << 30) - 1)

    def ticks_add(self, t, d):
        return (t + d) & ((1 << 30) - 1)

    def ticks_diff(self, a, b):
        half = 1 << 29
        return ((a - b + half) & ((1 << 30) - 1)) - half

    def sleep_ms(self, ms):
        time.sleep(ms / 1000)


class PrintDog:
    def __getattr__(self, name):
        def call(*args):
            print("  MechDog.%s%s" % (name, args))
            return True
        return call


def main():
    robot = Robot(config, Motion(PrintDog()), Clock(), lambda: 7400, lambda: (0.0, 0.0))
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", config.CMD_PORT))
    sock.setblocking(False)
    print("가짜 로봇 %s 대기 중 (UDP %d)" % (config.ROBOT_ID, config.CMD_PORT))
    while True:
        try:
            while True:
                data, addr = sock.recvfrom(256)
                robot.handle(data, addr)
        except BlockingIOError:
            pass
        robot.tick(True)
        if robot.telemetry_due():
            dest = robot.telemetry_dest()
            if dest:
                sock.sendto(robot.telemetry().encode(), dest)
        time.sleep(0.005)


if __name__ == "__main__":
    main()
