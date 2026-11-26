"""PC 로봇 조종·모니터링 화면 (PC에서 로봇에 바로 연결하는 시험·조종 도구).

브라우저는 UDP를 못 보내므로 이 서버가 중간에서 저장소의 통신 규약(ai/protocol.md)대로
로봇 메인 보드에 HELLO/MOVE/STOP/ESTOP/RESET 을 보냅니다. 안전 규칙은 dashboard/robot_link.py 를 그대로 씁니다.
- 이동은 버튼을 누르고 있는 동안만(0.3초 안에 다시 안 오면 STOP)
- 로봇은 부팅 시 잠겨 있고, 사람이 '잠금 해제'를 눌러야 움직임
- 화면이 닫히거나 서버가 끝나면 STOP

실행(비전 모듈 Wi-Fi):
  python -m dashboard.server --robot B --robot-ip auto --allow-real --cam http://192.168.5.1:81/stream
"""
import argparse
import json
import os
import re
import sqlite3
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import URLError
from urllib.request import urlopen

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import socket  # noqa: E402
from dashboard.robot_link import RobotLink, parse_telemetry  # noqa: E402
from dashboard.udp_transport import UdpTransport  # noqa: E402
from firmware.robot.python import config as settings, proto as wire  # noqa: E402
from dashboard.lidar.feed import LidarFeed  # noqa: E402
from dashboard.usb_camera import UsbCamera  # noqa: E402
from dashboard.camera_monitor import CameraMonitor  # noqa: E402
from dashboard.patrol import Patrol, PatrolVision  # noqa: E402
from dashboard.fall_events import DATA_DIR, FallEvents  # noqa: E402

MAX_BODY = 256
GREET_ACTION = "scrape_a_bow"  # 사람 인식 시 신호 (ai/mechdog-api.md 4.1)
GREET_WAIT_S = 2.0       # 감지 뒤 로봇이 멈춰 대기 상태가 되기를 기다리는 최대 시간
GREET_COOLDOWN_S = 10.0  # [가정] 인사가 끝난 뒤 다시 인사하지 않는 시간 (ai/scenario.md 3절)
GREET_LOST_S = 2.0       # 동작 최대 시간이 지나고도 끝남을 못 보면 추적을 그만두는 여유


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
    """일어서기(기본 자세)·동작 그룹 요청 추가. 로봇 규약의 POSE default = set_default_pose(),
    ACTION <이름> = action_run(이름)(허용 목록은 로봇이 다시 확인).
    잠금이 풀리고 신선한 대기 상태일 때 한 번만 보냅니다. 잠김·비상정지면 보내지 않습니다."""
    pending = None  # (마감, 명령, 인자): 다음 대기 주기에 한 번만 보냄

    def _can_stand(self):
        t = self.latest
        return (self.fresh() and not self.emergency and not t.latched and t.state == "idle"
                and t.battery_mv is not None and t.battery_mv >= settings.LOW_BATT_WARN_MV
                and not t.warnings.intersection({"batt_unknown", "batt_low", "lidar_uart", "lidar_backlog", "proto"}))

    def _request(self, name, arg):
        if not self._can_stand():
            raise ValueError("대기 상태·잠금 해제·배터리 상태를 확인하세요")
        self.stop()
        self.pending = (self.clock() + settings.HOST_INTENT_MS / 1000, name, arg)

    def request_stand(self):
        self._request("POSE", "default")

    def request_action(self, name):
        if name not in wire.ACTION_ALLOW:
            raise ValueError("허용되지 않은 동작 그룹")
        self._request("ACTION", name)

    def stop(self):
        self.pending = None
        super().stop()

    def estop(self):
        self.pending = None
        super().estop()

    def close(self):
        self.stop()
        super().close()

    def move(self, step, angle):
        self.pending = None
        if not self.fresh() or self.emergency or self.latest.latched:
            raise ValueError("로봇 연결과 잠금 상태를 확인하세요")
        super().move(step, angle)

    def observe(self, data):
        accepted = super().observe(data)
        if not accepted or not self._can_stand():
            self.pending = None
        return accepted

    def step(self):
        if not self._can_stand():
            self.pending = None
        super().step()

    def _idle_command(self):
        pending, self.pending = self.pending, None
        if pending is not None and self.clock() < pending[0]:
            return self._command(*pending[1:])
        return super()._idle_command()


class Console:
    def __init__(self, robot, transport, cam, lidar=None, usb_camera=None, monitor=None,
                 fall=None, events=None, *, greet=False, patrol=None, shared_feed=None, allow_real=False):
        self.lock = threading.Lock()
        self.transport = transport
        self.link = ConsoleLink(robot, transport.send, require_scan=False) if transport else None
        self.robot = robot
        self.cam = cam
        self.usb_camera = usb_camera
        self.monitor = monitor
        self.greet = greet
        self.patrol = patrol
        self.shared_feed = shared_feed
        self.allow_real = allow_real
        self.greet_until = None      # 인사를 보낼 마감(감지 직후 로봇이 대기 상태가 되길 기다림)
        self.greet_sent = None       # 인사를 보낸 시각. 끝나면 None
        self.greet_seen_action = False
        self.greet_block_until = -float("inf")
        self.greet_count = 0
        self.fall = fall
        self.events = events or FallEvents()
        self.samples = FallEvents(DATA_DIR / "sample-events.sqlite3")
        self.sample_lock = threading.Lock()
        self.hold_until = 0
        if fall and self.link:
            fall.on_fall = self.stop_for_fall
            last = self.events.last_detection(robot)
            if last:
                self.hold_until = time.monotonic() + max(0, min(30, last + 30 - time.time()))
        self.person_stop = self.obstacle_stop = False
        self.motion_epoch = 0
        self.manual_led = (0, 0, 0)
        self.applied_led = None
        self.lidar = lidar or LidarFeed()
        self.error = None
        self.running = True

    def stop_for_fall(self):
        with self.lock:
            self.end_patrol("쓰러짐 감지")
            self.hold_until = time.monotonic() + 30
            self.greet_until = self.greet_sent = None
            self.greet_seen_action = False
            self.motion_epoch += 1
            self.link.pending_led = None
            self.link.stop()

    def replay_sample(self):
        from dashboard.fall_detection import FallDetection
        if not self.sample_lock.acquire(blocking=False):
            raise ValueError("시연 사진 분석 중입니다.")
        try:
            frames = [(DATA_DIR / "samples/replay" / name).read_bytes() for name in ("first.jpg", "second.jpg")]
            self.samples.prepare()
            detector = FallDetection(None, self.samples, "공개 시연 사진")
            try:
                now, wall = time.monotonic(), time.time()
                for index, frame in enumerate(frames):
                    status, _ = detector.process(now + index / 3, wall + index / 3, frame)
                return status
            finally:
                detector.close()
        finally:
            self.sample_lock.release()

    def monitor_stop(self):
        video, _ = self.monitor.snapshot()
        t = self.link.latest if self.link.fresh() else None
        distance = t.sonar_mm if t else None
        person = self.person_stop if video["person"] is None else video["person"]
        obstacle = self.obstacle_stop
        if distance is not None and distance > 0:
            if distance <= 300:
                obstacle = True
            elif distance >= 400:
                obstacle = False
        new_person = person and not self.person_stop
        tripped = new_person or (obstacle and not self.obstacle_stop)
        self.person_stop, self.obstacle_stop = person, obstacle
        if tripped:
            self.motion_epoch += 1
            self.link.pending_led = None
            self.applied_led = None
            self.link.stop()
        if (new_person and self.greet and self.greet_sent is None and time.monotonic() >= self.hold_until
                and self.link.clock() >= self.greet_block_until):
            self.greet_until = self.link.clock() + GREET_WAIT_S
        return tripped

    def _greet_done(self, now):
        self.greet_sent = None
        self.greet_seen_action = False
        self.greet_block_until = now + GREET_COOLDOWN_S

    def monitor_greet(self):
        """사람이 새로 보이면 멈춘 뒤 인사(scrape_a_bow) → 끝나면 set_default_pose().
        수동 입력·사람 사라짐·잠김이면 보내지 않고, 인사 뒤 GREET_COOLDOWN_S 동안 다시 인사하지 않습니다."""
        link = self.link
        now = link.clock()
        t = link.latest if link.fresh() else None
        if self.greet_sent is not None:
            if t is None or link.emergency or t.latched:
                self._greet_done(now)  # 래치면 로봇이 stop_action + move(0, 0). 자세 요청 없음
            elif t.state == "action":
                self.greet_seen_action = True
            elif self.greet_seen_action and t.state == "idle":
                if link.intent is None:  # 수동 이동이 이어지면 로봇이 MOVE 전에 스스로 기본 자세를 잡음
                    try:
                        link.request_stand()
                    except ValueError:
                        pass
                self._greet_done(now)
            elif now - self.greet_sent > settings.ACTION_DURATION_MS[GREET_ACTION] / 1000 + GREET_LOST_S:
                self._greet_done(now)  # 명령 유실 등으로 동작을 못 봄
            return
        if self.greet_until is None:
            return
        if now > self.greet_until or not self.person_stop or link.intent is not None or link.emergency:
            self.greet_until = None  # 시간 초과·사람 사라짐·수동 조종이 우선
        elif link._can_stand():
            link.request_action(GREET_ACTION)
            self.greet_until = None
            self.greet_sent = now
            self.greet_seen_action = False
            self.greet_count += 1

    def monitor_led(self):
        if not self.link.fresh() or not self.link.latest.has_sonar or self.link.emergency:
            self.applied_led = None
            return
        desired = (255, 0, 0) if self.person_stop or self.obstacle_stop else self.manual_led
        if desired != self.applied_led:
            self.link.set_led(*desired)
            self.applied_led = desired

    def end_patrol(self, reason):
        if self.patrol and self.patrol.owner:
            self.patrol.stop(self.link, reason)
            self.motion_epoch += 1

    def check_patrol(self):
        link = self.link
        if not self.allow_real or not link or not link.fresh() or link.emergency or link.latest.latched:
            raise ValueError("실물 연결과 잠금 해제 상태를 확인하세요")
        t = link.latest
        if (t.state not in ("idle", "moving") or t.battery_mv is None or t.battery_mv < settings.LOW_BATT_WARN_MV
                or t.warnings.intersection({"batt_unknown", "batt_low", "lidar_uart", "lidar_backlog", "proto"})):
            raise ValueError("본체 상태 또는 배터리 경고")
        if not t.sonar_mm or t.sonar_mm <= 300:
            raise ValueError("전방 장애물 또는 초음파 확인 불가")
        if self.person_stop or self.obstacle_stop or time.monotonic() < self.hold_until:
            raise ValueError("감지 경고로 정지")

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
                            self.end_patrol("본체 상태 수신 오류")
                            self.link.stop()
                except OSError:
                    self.link.estop()
                try:
                    tripped = self.monitor and self.monitor_stop()
                    if self.patrol and self.patrol.owner:
                        try:
                            self.check_patrol()
                            self.patrol.tick(self.link)
                        except Exception as error:
                            self.end_patrol(str(error))
                    elif self.monitor and self.greet:
                        self.monitor_greet()
                    self.link.step()
                    if self.monitor and not tripped:
                        self.monitor_led()
                    self.error = None
                except Exception as error:  # 송신 실패: link 가 이미 ESTOP 쪽으로 바꿈
                    self.error = str(error)
            time.sleep(0.02)

    def state(self):
        with self.lock:
            fall_status = self.fall.snapshot()[0] if self.fall else None
            fall_fps = self.fall.feed.snapshot()[0]["fps"] if self.fall else None
            if self.link is None:
                return {"sensors_only": True, "robot": self.robot, "cam": self.cam,
                        "patrol": self.patrol.state() if self.patrol else None,
                        "usb_camera": self.usb_camera is not None, "fall": fall_status, "fall_fps": fall_fps}
            t = self.link.latest
            return {
                "patrol": self.patrol.state() if self.patrol else None,
                "allow_real": self.allow_real,
                "robot": self.link.robot,
                "status": self.link.status(),
                "fresh": self.link.fresh(),
                "emergency": self.link.emergency,
                "fault": self.link.fault,
                "error": self.error,
                "cam": self.cam,
                "fall": fall_status,
                "fall_fps": fall_fps,
                "fall_hold": max(0, self.hold_until - time.monotonic()),
                "epoch": self.motion_epoch,
                "usb_camera": self.usb_camera is not None,
                "monitor": ({
                    **self.monitor.snapshot()[0],
                    "person_stop": self.person_stop,
                    "obstacle_stop": self.obstacle_stop,
                    "epoch": self.motion_epoch,
                    "override": bool((self.person_stop or self.obstacle_stop) and self.link.intent),
                    "greet": ("off" if not self.greet else "greeting" if self.greet_sent is not None
                              else "waiting" if self.greet_until is not None
                              else "cooldown" if self.link.clock() < self.greet_block_until else "ready"),
                    "greet_count": self.greet_count,
                } if self.monitor else None),
                "robot_ip": self.transport.peer[0] if self.transport.peer else None,
                "tel": None if t is None else {
                    "state": t.state, "latched": t.latched, "reason": t.reason,
                    "battery_mv": t.battery_mv, "tilt": t.tilt,
                    "warnings": sorted(t.warnings), "last_seq": t.last_seq,
                    "sonar_mm": t.sonar_mm, "has_sonar": t.has_sonar,
                },
                "led": self.link.led,
            }

    def command(self, path, body):
        with self.lock:
            if path.startswith("/api/patrol/"):
                if not self.patrol or not self.running:
                    raise ValueError("Wi-Fi 카메라와 AprilTag 지원 OpenCV가 필요합니다")
                if path == "/api/patrol/calibrate":
                    return self.patrol.calibrate()
                if path == "/api/patrol/start":
                    self.check_patrol()
                    if body.get("epoch") != self.motion_epoch or not self.link._can_stand() or self.link.intent:
                        raise ValueError("본체가 정지한 뒤 다시 시작하세요")
                    self.patrol.start(body)
                    self.motion_epoch += 1
                    self.greet_until = None
                    return
                if path == "/api/patrol/heartbeat":
                    if not self.patrol.owner or body.get("owner") != self.patrol.owner:
                        raise ValueError("순찰 세션이 종료되었습니다")
                    if time.monotonic() >= self.patrol.lease:
                        self.end_patrol("조종 화면 연결 만료")
                        raise ValueError("조종 화면 연결 만료")
                    self.patrol.lease = time.monotonic() + .9
                    return
                raise KeyError(path)
            if self.link is None:
                raise ValueError("sensor-only mode")
            if not self.running:
                raise ValueError("console is closing")
            if path in ("/api/move", "/api/stop", "/api/estop"):
                self.greet_until = None  # 사람 입력이 보내기 전 인사보다 우선
            if path in ("/api/move", "/api/stop", "/api/estop", "/api/reset", "/api/stand"):
                self.end_patrol("운영자 개입")
                if path in ("/api/stop", "/api/estop"):
                    self.motion_epoch += 1
            if path in ("/api/move", "/api/stand", "/api/reset") and time.monotonic() < self.hold_until:
                raise ValueError("쓰러짐 감지로 30초 정지 중입니다.")
            if path == "/api/move":
                if (self.monitor or self.fall) and body.get("epoch") != self.motion_epoch:
                    raise ValueError("감지로 정지했습니다. 방향을 다시 누르세요")
                self.link.move(body["step"], body["angle"])
            elif path == "/api/stop":
                self.link.stop()
            elif path == "/api/estop":
                self.link.estop()
            elif path == "/api/stand":
                self.link.request_stand()
            elif path == "/api/led":
                if self.monitor and (self.person_stop or self.obstacle_stop):
                    raise ValueError("감지 경고 중에는 빨간색을 유지합니다")
                self.link.set_led(body["r"], body["g"], body["b"])
                if self.monitor:
                    self.manual_led = self.applied_led = self.link.pending_led
            elif path == "/api/reset":
                self.link.request_reset()  # 잠김·배터리 조건이 안 맞으면 ValueError
            else:
                raise KeyError(path)

    def close(self):
        with self.lock:
            self.running = False
            if self.link is not None:
                try:
                    self.link.close()
                except Exception:
                    pass


def make_handler(console):
    page_path = os.path.join(HERE, "index.html")  # 요청마다 읽어서 화면 수정이 새로고침만으로 반영됨

    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(2)

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

        def _reject_post(self, status, reason):
            self.close_connection = True
            self._send(status, {"error": reason})
            self.wfile.flush()
            # Windows can reset the HTTP response when request bytes are unread.
            try:
                self.connection.shutdown(socket.SHUT_WR)
                self.connection.settimeout(0.05)
                self.rfile.read1(MAX_BODY)
            except OSError:
                pass

        def do_GET(self):
            if not self._local_request():
                return self._send(403, {"error": "local console only"})
            if self.path in ("/", "/index.html"):
                with open(page_path, "rb") as f:
                    return self._send(200, f.read(), "text/html; charset=utf-8")
            if self.path == "/api/state":
                return self._send(200, console.state())
            if self.path == "/api/patrol/frame" and console.patrol:
                frame, jpeg = console.patrol.vision.snapshot()
                if frame and time.monotonic() - frame[1] < 1:
                    return self._send(200, jpeg, "image/jpeg")
                return self._send(503, {"error": "최신 영상 없음"})
            if self.path.startswith("/api/patrol/marker/") and console.patrol:
                match = re.fullmatch(r"/api/patrol/marker/([0-9]{1,3})", self.path)
                if not match or int(match[1]) >= 587:
                    return self._send(400, {"error": "태그 번호 범위는 0~586입니다"})
                vision = console.patrol.vision
                marker = vision.cv.aruco.generateImageMarker(vision.dictionary, int(match[1]), 640)
                marker = vision.cv.copyMakeBorder(marker, 80, 80, 80, 80, vision.cv.BORDER_CONSTANT, value=255)
                return self._send(200, vision.cv.imencode(".png", marker)[1].tobytes(), "image/png")
            archive = console.samples if self.path.startswith("/api/falls-samples") else console.events
            page = re.fullmatch(r"/api/falls(?:-samples)?(?:\?before=([1-9][0-9]{0,17}))?", self.path)
            photo = re.fullmatch(r"/api/falls(?:-samples)?/([1-9][0-9]{0,17})/photos/([01])", self.path)
            try:
                if page:
                    before = int(page[1]) if page[1] else 2**63 - 1
                    return self._send(200, archive.page(before))
                if photo:
                    return self._send(200, archive.photo(int(photo[1]), int(photo[2])), "image/jpeg")
            except KeyError:
                return self._send(404, {"error": "사진 없음"})
            except sqlite3.Error:
                return self._send(503, {"error": "사건 기록을 읽을 수 없습니다"})
            if self.path == "/api/lidar":
                return self._send(200, console.lidar.snapshot())
            if self.path == "/api/camera" and (console.fall or console.monitor):
                _, jpeg = (console.fall or console.monitor).snapshot()
                if jpeg is None and console.fall:
                    _, jpeg = console.fall.feed.snapshot()
                if jpeg is None:
                    return self._send(503, {"error": "최신 영상 없음"})
                return self._send(200, jpeg, "image/jpeg")
            if self.path == "/api/camera" and console.usb_camera:
                jpeg, error = console.usb_camera.snapshot()
                if jpeg is not None:
                    return self._send(200, jpeg, "image/jpeg")
                return self._send(503, {"error": error})
            if self.path == "/api/camera" and console.shared_feed:
                _, jpeg = console.shared_feed.snapshot()
                if jpeg:
                    return self._send(200, jpeg, "image/jpeg")
                return self._send(503, {"error": "최신 영상 없음"})
            self._send(404, {"error": "not found"})

        def do_POST(self):
            if not self._local_request():
                return self._reject_post(403, "local console only")
            if self.headers.get_content_type() != "application/json":
                return self._reject_post(415, "JSON required")
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                return self._reject_post(400, "invalid length")
            if length < 0:
                return self._reject_post(400, "invalid length")
            review = re.fullmatch(r"/api/falls(?:-samples)?/([1-9][0-9]{0,17})/review", self.path)
            if length > (16384 if review else MAX_BODY):
                return self._reject_post(413, "too large")
            try:
                body = json.loads(self.rfile.read(length) or b"{}")
                if not isinstance(body, dict):
                    raise ValueError("JSON object required")
                if self.path == "/api/falls-samples/replay":
                    return self._send(200, {"status": console.replay_sample()})
                if review:
                    archive = console.samples if self.path.startswith("/api/falls-samples/") else console.events
                    archive.review(int(review[1]), body.get("verdict"), body.get("note"))
                else:
                    console.command(self.path, body)
            except (FileNotFoundError, ImportError):
                return self._send(503, {"error": "시연 사진 또는 감지 모델이 준비되지 않았습니다."})
            except (OSError, RuntimeError, sqlite3.Error):
                if self.path.startswith("/api/patrol/"):
                    return self._send(503, {"error": "도착 기준을 저장할 수 없습니다"})
                return self._send(503, {"error": "사진 분석 또는 저장에 실패했습니다."})
            except KeyError:
                return self._send(404, {"error": "not found"})
            except (ValueError, TypeError) as error:
                return self._send(400, {"error": str(error)})
            self._send(200, {"ok": True})

    return Handler


def hotspot_camera_url(robot):
    host = f"mechdog-{robot.lower()}-cam.local"
    try:
        with urlopen(f"http://{host}/status", timeout=3) as response:
            status = json.load(response)
        if status["robot"] == robot:
            return f"http://{status['wifi']['ip']}:{status['stream']['port']}/stream"
    except (URLError, TimeoutError, ValueError, KeyError, TypeError):
        pass
    return f"http://{host}:81/stream"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--robot", choices=("A", "B"), default="A")
    p.add_argument("--robot-ip",
                   help="로봇 IP. 'auto' 면 같은 Wi-Fi에서 자동으로 찾음(--broadcast 사용)")
    p.add_argument("--broadcast", help="자동 찾기용 방송 주소")
    p.add_argument("--hotspot", action="store_true",
                   help="Windows 모바일 핫스팟에서 로봇과 비전 모듈 자동 연결")
    p.add_argument("--allow-real", action="store_true", help="실제 로봇에 보내기 허용")
    p.add_argument("--sensors-only", action="store_true", help="카메라·라이다 표시, 본체 UDP 소켓 없음")
    p.add_argument("--monitor", action="store_true", help="Wi-Fi 영상 사람 감지와 초음파 정지 활성화")
    p.add_argument("--greet", action="store_true", help="--monitor 에서 사람을 새로 보면 멈춘 뒤 인사(scrape_a_bow)")
    p.add_argument("--fall-detection", action="store_true", help="Wi-Fi 영상 쓰러짐 감지 및 검토 사진 저장")
    camera_source = p.add_mutually_exclusive_group()
    camera_source.add_argument("--cam", default="", help="카메라 영상 주소 예: http://192.168.5.1:81/stream")
    camera_source.add_argument("--cam-usb", metavar="COM_PORT", help="USB JPEG 펌웨어가 설치된 ESP32-S3")
    p.add_argument("--port", type=int, default=8090)
    lidar_source = p.add_mutually_exclusive_group()
    lidar_source.add_argument("--lidar-usb", metavar="COM_PORT", help="확인된 A1M8 어댑터")
    lidar_source.add_argument("--lidar-tcp", metavar="HOST", help="라이다 중계 주소")
    lidar_source.add_argument("--relay-lidar", action="store_true", help="--robot-ip와 같은 본체의 중계 사용")
    p.add_argument("--lidar-port", type=int, default=settings.LIDAR_TCP_PORT)
    a = p.parse_args()
    if a.monitor and (a.sensors_only or a.cam_usb or not (a.cam or a.hotspot)):
        p.error("--monitor는 Wi-Fi 카메라와 본체 연결 모드가 필요합니다")
    if a.greet and not a.monitor:
        p.error("--greet에는 --monitor가 필요합니다")
    if a.fall_detection and (a.cam_usb or not (a.cam or a.hotspot)):
        p.error("--fall-detection에는 Wi-Fi 카메라(--cam 또는 --hotspot)가 필요합니다")
    cv2 = None
    if a.monitor or a.fall_detection or a.cam or a.hotspot:
        try:
            import cv2
        except ImportError:
            if a.monitor or a.fall_detection:
                p.error("영상 감지에는 OpenCV 설치가 필요합니다. README를 확인하세요.")
    a.robot_ip = a.robot_ip or ("auto" if a.hotspot else "127.0.0.1")
    a.broadcast = a.broadcast or ("192.168.137.255" if a.hotspot else "192.168.5.255")
    if a.relay_lidar and a.robot_ip == "auto":
        p.error("--relay-lidar에는 명시적 --robot-ip가 필요합니다")
    if a.sensors_only and a.allow_real:
        p.error("--sensors-only는 --allow-real과 함께 쓸 수 없습니다")
    if a.cam_usb and a.lidar_usb and a.cam_usb.upper() == a.lidar_usb.upper():
        p.error("카메라와 LiDAR의 COM 포트는 달라야 합니다")
    lidar = LidarFeed(usb=a.lidar_usb, tcp=a.robot_ip if a.relay_lidar else a.lidar_tcp, port=a.lidar_port)

    if a.sensors_only:
        transport = None
    elif a.robot_ip == "auto":
        if not a.allow_real:
            raise SystemExit("--robot-ip auto 는 실제 로봇용이라 --allow-real 이 필요합니다")
        transport = AutoTransport(a.robot, a.broadcast)
    else:
        transport = UdpTransport(a.robot_ip, allow_real=a.allow_real)
    camera = UsbCamera(a.cam_usb) if a.cam_usb else None
    cam = hotspot_camera_url(a.robot) if a.hotspot and not (a.cam or camera) else a.cam
    patrol_supported = bool(cam and hasattr(getattr(cv2, "aruco", None), "ArucoDetector"))
    feed = CameraMonitor(cam, cv2, a.monitor, a.robot) if patrol_supported or a.monitor or a.fall_detection else None
    patrol = Patrol(PatrolVision(feed, cv2), DATA_DIR / f"patrol-{a.robot}.sqlite3") if patrol_supported else None
    events = FallEvents()
    fall = None
    if a.fall_detection:
        try:
            from dashboard.fall_detection import FallDetection
            events.prepare()
            fall = FallDetection(feed, events, a.robot)
        except (ImportError, OSError, ValueError, RuntimeError, sqlite3.Error) as error:
            p.error(f"쓰러짐 감지 초기화 실패: {error}")
    console = Console(a.robot, transport, cam, lidar, camera, feed if a.monitor else None, fall, events,
                      greet=a.greet, patrol=patrol, shared_feed=feed, allow_real=a.allow_real)
    camera_worker = lidar_worker = None
    try:
        with ThreadingHTTPServer(("127.0.0.1", a.port), make_handler(console)) as server:
            if transport:
                threading.Thread(target=console.loop, daemon=True).start()
            if lidar.source:
                lidar_worker = threading.Thread(target=lidar.run, daemon=True)
                lidar_worker.start()
            if camera:
                camera_worker = threading.Thread(target=camera.run, daemon=True)
                camera_worker.start()
            if feed:
                feed.start()
            if patrol:
                patrol.vision.start()
            if fall:
                fall.worker.start()
            print("열기: http://127.0.0.1:%d  (로봇 %s @ %s)" % (server.server_port, a.robot, a.robot_ip))
            server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        console.close()
        if feed:
            feed.stop_event.set()
        if fall and fall.worker.is_alive():
            fall.worker.join()
        if transport:
            transport.close()
        lidar.stop_event.set()
        if camera:
            camera.stop_event.set()
        if lidar_worker:
            lidar_worker.join(7)
        if camera_worker:
            camera_worker.join(2)


if __name__ == "__main__":
    main()
