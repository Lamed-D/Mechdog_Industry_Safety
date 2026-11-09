"""대시보드 실행.

    python -m dashboard.web.run --sim                 # 가짜 로봇으로 화면 확인 (http://127.0.0.1:8000)
    python -m dashboard.web.run --sim --host 0.0.0.0  # 같은 공유기의 다른 기기에서 열기

실물 점검은 --allow-real --robot-a <IP> --robot-b <IP>로 명시합니다. 이동·자세는 정지로 처리합니다.
"""
import argparse
import sys
import threading
import time

from dashboard.core import DashboardCore, EventLog
from dashboard.web.server import DashboardServer
from dashboard.web.sim import SimLink, start_loop
from scenario.machine import Scenario


def build_sim(log_path=":memory:"):
    links = {"A": SimLink("A"), "B": SimLink("B")}
    core = DashboardCore(Scenario(), links, EventLog(log_path))
    return core, links


def main(argv=None):
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--sim", action="store_true", help="가짜 로봇 사용")
    mode.add_argument("--allow-real", action="store_true", help="사용자 실물 점검: HELLO/STOP/ESTOP/명시적 RESET")
    parser.add_argument("--robot-a", help="로봇 A의 IPv4")
    parser.add_argument("--robot-b", help="로봇 B의 IPv4")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--token", help="조작(전체 정지 제외)에 필요한 토큰")
    parser.add_argument("--log", default=":memory:", help="SQLite 기록 파일(저장소 밖 경로)")
    args = parser.parse_args(argv)
    lock = threading.Lock()
    adapter = None
    if args.sim:
        core, links = build_sim(args.log)
    else:
        if not args.robot_a or not args.robot_b:
            parser.error("실물 점검에는 --robot-a와 --robot-b가 필요합니다")
        if not args.token:
            parser.error("실물 점검에는 사용자 조작 토큰 --token이 필요합니다")
        from host.robot_hub import RobotHub
        from dashboard.web.robot_adapter import RobotAdapter
        adapter = RobotAdapter(RobotHub({"A": args.robot_a, "B": args.robot_b}, allow_real=True))
        core = DashboardCore(Scenario(), adapter.links, EventLog(args.log))
    server = None
    stop_event = thread = None
    try:
        server = DashboardServer(core, lock, args.host, args.port, args.token).start()
        if adapter:
            from dashboard.web.robot_adapter import start_loop as start_real_loop
            stop_event, thread = start_real_loop(adapter, core, lock)
        else:
            stop_event, thread = start_loop(core, links, lock)
        print("dashboard (%s): http://%s:%d" % (("stationary" if adapter else "sim"), *server.address))
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        if stop_event:
            stop_event.set()
            thread.join(2)
        elif adapter:
            adapter.close()
        if server:
            server.stop()
        core.log.close()


if __name__ == "__main__":
    main()
