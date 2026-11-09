"""대시보드 실행.

    python -m dashboard.web.run --sim                 # 가짜 로봇으로 화면 확인 (http://127.0.0.1:8000)
    python -m dashboard.web.run --sim --host 0.0.0.0  # 같은 공유기의 다른 기기에서 열기

실제 로봇 연결(RobotLink + UDP, 텔레메트리 소켓 공유·로봇별 분배)은 다음 단계에서 추가합니다.
그전까지 --sim 없이 실행하면 멈춥니다(실물 연결로 오해하지 않게).
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
    parser.add_argument("--sim", action="store_true", help="가짜 로봇 사용(필수, 실물 연결은 아직 없음)")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--token", help="조작(전체 정지 제외)에 필요한 토큰")
    parser.add_argument("--log", default=":memory:", help="SQLite 기록 파일(저장소 밖 경로)")
    args = parser.parse_args(argv)
    if not args.sim:
        sys.exit("실물 연결은 아직 없습니다. 화면 확인은 --sim 으로 실행하세요.")
    core, links = build_sim(args.log)
    lock = threading.Lock()
    stop_event, _ = start_loop(core, links, lock)
    server = DashboardServer(core, lock, args.host, args.port, args.token).start()
    print("dashboard (sim): http://%s:%d" % server.address)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        stop_event.set()
        server.stop()


if __name__ == "__main__":
    main()
