"""가짜 로봇: 실제 로봇 코드(robot/core.py)를 PC에서 돌리고 MechDog 호출은 화면에 찍기만 합니다.

실행: python -m test_PC.robot_console.fake_robot   (127.0.0.1:9100 에서 명령 받음)
"""
import argparse
import os
import secrets as _stdlib_secrets  # noqa: F401  robot/secrets.py 에 가려지지 않게
import socket
import sys
import time

from tests.fakes.HW_MechDog import MechDog

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "robot"))

import config  # noqa: E402
from comm import MAX_DATAGRAM, POLL_LIMIT  # noqa: E402
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--robot", choices=("A", "B"), default="A")
    config.ROBOT_ID = parser.parse_args().robot
    dog = MechDog()
    robot = Robot(config, Motion(dog), Clock(), lambda: 7400, lambda: (0.0, 0.0))
    last_call = None
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.bind(("127.0.0.1", config.CMD_PORT))
            sock.setblocking(False)
            print("가짜 로봇 %s 대기 중 (UDP %d)" % (config.ROBOT_ID, config.CMD_PORT))
            while True:
                for _ in range(POLL_LIMIT):
                    try:
                        data, addr = sock.recvfrom(MAX_DATAGRAM)
                    except (BlockingIOError, ConnectionResetError):
                        break
                    robot.handle(data, addr)
                robot.tick(True)
                if robot.telemetry_due():
                    dest = robot.telemetry_dest()
                    if dest:
                        sock.sendto(robot.telemetry().encode(), dest)
                for call in dog.calls:
                    name, args = call
                    if name != "action_is_over" and call != last_call:
                        print("  MechDog.%s%s" % (name, args))
                        last_call = call
                dog.calls.clear()
                time.sleep(0.005)
    except KeyboardInterrupt:
        pass
    finally:
        robot.fail_safe()


if __name__ == "__main__":
    main()
