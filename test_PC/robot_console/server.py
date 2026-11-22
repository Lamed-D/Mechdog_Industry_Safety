"""PC 로봇 조종·모니터링 화면 (PC에서 로봇에 바로 연결하는 시험·조종 도구).

브라우저는 UDP를 못 보내므로 이 서버가 중간에서 저장소의 통신 규약(docs/protocol.md)대로
로봇 메인 보드에 HELLO/MOVE/STOP/ESTOP/RESET 을 보냅니다. 안전 규칙은 host/robot_link.py 를 그대로 씁니다.
- 이동은 버튼을 누르고 있는 동안만(0.3초 안에 다시 안 오면 STOP)
- 로봇은 부팅 시 잠겨 있고, 사람이 '잠금 해제'를 눌러야 움직임
- 화면이 닫히거나 서버가 끝나면 STOP

실행 (가짜 로봇):  python -m test_PC.robot_console.fake_robot
                  python -m test_PC.robot_console.server
실물 로봇(비전 모듈 Wi-Fi):
  python -m test_PC.robot_console.server --robot B --robot-ip auto --allow-real --cam http://192.168.5.1:81/stream
"""
import argparse
import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)

import socket  # noqa: E402
from host.robot_link import RobotLink, parse_telemetry  # noqa: E402
from host.udp_transport import UdpTransport  # noqa: E402
from robot import config as settings  # noqa: E402
from test_PC.robot_console.lidar import LidarFeed  # noqa: E402

MAX_BODY = 256


class AutoTransport:
    """로봇 IP를 모를 때: 같은 Wi-Fi에 방송(broadcast)으로 HELLO/STOP을 보내고,
    처음 답한 해당 ID 로봇의 IP로 고정합니다. 고정 전에는 그 로봇의 TEL 말고는 받지 않습니다.
    RobotLink 는 신선한 TEL이 오기 전에는 MOVE/RESET 을 보내지 않으므로 이동 명령은 고정 뒤에만 나갑니다."""

    def __init__(self, robot, broadcast, port=settings.CMD_PORT, receive_port=settings.TEL_PORT):
        self.robot = robot.encode()
        self.target = (broadcast, port)
        self.port = port
        self.peer = None
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            self.socket.bind(("0.0.0.0", receive_port))
            self.socket.setblocking(False)
        except Exception:
            self.socket.close()
            raise

    def send(self, data):
        self.socket.sendto(data, self.peer or self.target)

    def receive(self):
        for _ in range(16):
            try:
                data, peer = self.socket.recvfrom(2048)
            except (BlockingIOError, ConnectionResetError):
                break
            if self.peer is None:
                try:
                    telemetry = parse_telemetry(data)
                except ValueError:
                    continue
                if telemetry.robot.encode() == self.robot and peer[1] == self.port:
                    self.peer = peer
                    print("로봇 찾음:", peer[0])
                else:
                    continue
            if peer == self.peer:
                yield data

    def close(self):
        self.socket.close()


class ConsoleLink(RobotLink):
    """일어서기(기본 자세) 요청 추가. 로봇 규약의 POSE default = set_default_pose().
    잠금이 풀리고 신선한 상태일 때 한 번만 보냅니다. 잠김·비상정지면 보내지 않습니다."""
    pending_pose = None

    def _can_stand(self):
        t = self.latest
        return (self.fresh() and not self.emergency and not t.latched and t.state == "idle"
                and t.battery_mv is not None and t.battery_mv >= settings.LOW_BATT_WARN_MV
                and not t.warnings.intersection({"batt_unknown", "batt_low", "lidar_uart", "lidar_backlog", "proto"}))

    def request_stand(self):
        if not self._can_stand():
            raise ValueError("대기 상태·잠금 해제·배터리 상태를 확인하세요")
        self.stop()
        self.pending_pose = self.clock() + settings.HOST_INTENT_MS / 1000

    def stop(self):
        self.pending_pose = None
        super().stop()

    def estop(self):
        self.pending_pose = None
        super().estop()

    def close(self):
        self.stop()
        super().close()

    def move(self, step, angle):
        self.pending_pose = None
        super().move(step, angle)

    def observe(self, data):
        accepted = super().observe(data)
        if not accepted or not self._can_stand():
            self.pending_pose = None
        return accepted

    def step(self):
        if not self._can_stand():
            self.pending_pose = None
        super().step()

    def _idle_command(self):
        deadline, self.pending_pose = self.pending_pose, None
        if deadline is not None and self.clock() < deadline:
            return self._command("POSE", "default")
        return super()._idle_command()


class Console:
    def __init__(self, robot, transport, cam, lidar=None):
        self.lock = threading.Lock()
        self.transport = transport
        self.link = ConsoleLink(robot, transport.send, require_scan=False)  # 라이다 없이 수동 조종
        self.cam = cam
        self.lidar = lidar or LidarFeed()
        self.error = None
        self.running = True

    def loop(self):
        while True:
            with self.lock:
                if not self.running:
                    return
                try:
                    for data in self.transport.receive():
                        try:
                            self.link.observe(data)
                        except ValueError:
                            self.link.stop()
                except OSError:
                    self.link.estop()
                try:
                    self.link.step()
                    self.error = None
                except Exception as error:  # 송신 실패: link 가 이미 ESTOP 쪽으로 바꿈
                    self.error = str(error)
            time.sleep(0.02)

    def state(self):
        with self.lock:
            t = self.link.latest
            return {
                "robot": self.link.robot,
                "status": self.link.status(),
                "fresh": self.link.fresh(),
                "emergency": self.link.emergency,
                "fault": self.link.fault,
                "error": self.error,
                "cam": self.cam,
                "robot_ip": self.transport.peer[0] if self.transport.peer else None,
                "tel": None if t is None else {
                    "state": t.state, "latched": t.latched, "reason": t.reason,
                    "battery_mv": t.battery_mv, "tilt": t.tilt,
                    "warnings": sorted(t.warnings), "last_seq": t.last_seq,
                },
            }

    def command(self, path, body):
        with self.lock:
            if not self.running:
                raise ValueError("console is closing")
            if path == "/api/move":
                self.link.move(body["step"], body["angle"])
            elif path == "/api/stop":
                self.link.stop()
            elif path == "/api/estop":
                self.link.estop()
            elif path == "/api/stand":
                self.link.request_stand()
            elif path == "/api/reset":
                self.link.request_reset()  # 잠김·배터리 조건이 안 맞으면 ValueError
            else:
                raise KeyError(path)

    def close(self):
        with self.lock:
            self.running = False
            try:
                self.link.close()
            except Exception:
                pass


def make_handler(console):
    page_path = os.path.join(HERE, "index.html")  # 요청마다 읽어서 화면 수정이 새로고침만으로 반영됨

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _send(self, code, body, ctype="application/json; charset=utf-8"):
            data = body if isinstance(body, bytes) else json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def _local_request(self):
            host = f"127.0.0.1:{self.server.server_port}"
            origin = self.headers.get("Origin")
            return self.headers.get("Host") == host and origin in (None, f"http://{host}")

        def do_GET(self):
            if not self._local_request():
                return self._send(403, {"error": "local console only"})
            if self.path in ("/", "/index.html"):
                with open(page_path, "rb") as f:
                    return self._send(200, f.read(), "text/html; charset=utf-8")
            if self.path == "/api/state":
                return self._send(200, console.state())
            if self.path == "/api/lidar":
                return self._send(200, console.lidar.snapshot())
            self._send(404, {"error": "not found"})

        def do_POST(self):
            if not self._local_request():
                return self._send(403, {"error": "local console only"})
            if self.headers.get_content_type() != "application/json":
                return self._send(415, {"error": "JSON required"})
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                return self._send(400, {"error": "invalid length"})
            if length < 0:
                return self._send(400, {"error": "invalid length"})
            if length > MAX_BODY:
                return self._send(413, {"error": "too large"})
            try:
                body = json.loads(self.rfile.read(length) or b"{}")
                if not isinstance(body, dict):
                    raise ValueError("JSON object required")
                console.command(self.path, body)
            except KeyError:
                return self._send(404, {"error": "not found"})
            except (ValueError, TypeError) as error:
                return self._send(400, {"error": str(error)})
            self._send(200, {"ok": True})

    return Handler


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--robot", choices=("A", "B"), default="A")
    p.add_argument("--robot-ip", default="127.0.0.1",
                   help="로봇 IP. 'auto' 면 같은 Wi-Fi에서 자동으로 찾음(--broadcast 사용)")
    p.add_argument("--broadcast", default="192.168.5.255", help="자동 찾기용 방송 주소(비전 모듈 Wi-Fi 기준)")
    p.add_argument("--allow-real", action="store_true", help="실제 로봇에 보내기 허용")
    p.add_argument("--cam", default="", help="카메라 영상 주소 예: http://192.168.5.1:81/stream")
    p.add_argument("--port", type=int, default=8090)
    lidar_source = p.add_mutually_exclusive_group()
    lidar_source.add_argument("--lidar-usb", metavar="COM_PORT", help="확인된 A1M8 어댑터")
    lidar_source.add_argument("--lidar-tcp", metavar="HOST", help="라이다 중계 또는 모의 서버 주소")
    p.add_argument("--lidar-port", type=int, default=settings.LIDAR_TCP_PORT)
    a = p.parse_args()
    lidar = LidarFeed(usb=a.lidar_usb, tcp=a.lidar_tcp, port=a.lidar_port)

    if a.robot_ip == "auto":
        if not a.allow_real:
            raise SystemExit("--robot-ip auto 는 실제 로봇용이라 --allow-real 이 필요합니다")
        transport = AutoTransport(a.robot, a.broadcast)
    else:
        transport = UdpTransport(a.robot_ip, allow_real=a.allow_real)
    console = Console(a.robot, transport, a.cam, lidar)
    lidar_worker = None
    try:
        with ThreadingHTTPServer(("127.0.0.1", a.port), make_handler(console)) as server:
            worker = threading.Thread(target=console.loop, daemon=True)
            worker.start()
            if lidar.source:
                lidar_worker = threading.Thread(target=lidar.run, daemon=True)
                lidar_worker.start()
            print("열기: http://127.0.0.1:%d  (로봇 %s @ %s)" % (server.server_port, a.robot, a.robot_ip))
            server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        console.close()
        transport.close()
        lidar.stop_event.set()
        if lidar_worker:
            lidar_worker.join(7)


if __name__ == "__main__":
    main()
