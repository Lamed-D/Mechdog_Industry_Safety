import socket
import subprocess
import sys
import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from host.lidar.rplidar_protocol import Sample
from test_PC.robot_console.lidar import LidarFeed
from test_PC.robot_console.make_robot_files import UPLOAD_ORDER, render
from test_PC.robot_console.server import AutoTransport, Console, ConsoleLink, make_handler

ROOT = Path(__file__).resolve().parents[2]


class Clock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


def tel(seq, latched, reason, boot, battery=7400, tseq=1, uptime=1000):
    state = "stopped" if latched else "idle"
    return ("TEL|B|%d|%d|%s|%d|%s|%d|0.0|0.0|%d|%s|none|$"
            % (tseq, seq, state, 1 if latched else 0, reason, battery, uptime, boot)).encode()


class ConsoleLinkTests(unittest.TestCase):
    def setUp(self):
        self.sent = []
        self.clock = Clock()
        self.link = ConsoleLink("B", self.sent.append, clock=self.clock, boot_id="t1", require_scan=False)

    def step(self):
        self.clock.now += 0.11
        self.link.step()
        return self.sent[-1]

    def test_stand_refused_while_latched(self):
        self.link.observe(tel(0, True, "boot", "t1"))
        with self.assertRaises(ValueError):
            self.link.request_stand()

    def test_stand_sends_pose_default_once_after_unlock(self):
        self.link.observe(tel(0, False, "none", "t1"))
        self.link.request_stand()
        self.assertEqual(self.step(), b"CMD|POSE|B|1|default|$")
        self.link.observe(tel(1, False, "none", "t1", tseq=2, uptime=1100))
        self.assertEqual(self.step(), b"CMD|STOP|B|2|$")

    def test_estop_cancels_pending_stand(self):
        self.link.observe(tel(0, False, "none", "t1"))
        self.link.request_stand()
        self.link.estop()
        self.assertEqual(self.step(), b"CMD|ESTOP|B|1|$")
        self.assertFalse(self.link.pending_pose)

    def test_stop_cancels_pending_stand(self):
        self.link.observe(tel(0, False, "none", "t1"))
        self.link.request_stand()
        self.link.stop()
        self.assertEqual(self.step(), b"CMD|STOP|B|1|$")
        self.assertIsNone(self.link.pending_pose)

    def test_close_cancels_pending_stand_even_with_fresh_telemetry(self):
        self.link.observe(tel(0, False, "none", "t1"))
        self.link.request_stand()
        self.link.close()
        self.assertEqual(self.sent, [b"CMD|STOP|B|1|$"])
        self.assertIsNone(self.link.pending_pose)

    def test_pose_expiry_and_telemetry_loss(self):
        self.link.observe(tel(0, False, "none", "t1"))
        self.link.request_stand()
        self.clock.now += 0.21
        self.assertEqual(self.step(), b"CMD|STOP|B|1|$")
        self.link.observe(tel(1, False, "none", "t1", tseq=2))
        self.link.request_stand()
        self.clock.now += 1
        self.link.step()
        self.assertIn(b"CMD|ESTOP|B|2|$", self.sent)
        self.assertIsNone(self.link.pending_pose)


class ConsoleHttpTests(unittest.TestCase):
    def test_scan_endpoint_clears_stale_and_disconnected_points(self):
        clock = Clock()
        feed = LidarFeed(tcp="127.0.0.1", clock=clock)
        for sample in (Sample(True, 0, 3000, 10), Sample(False, 90, 0, 10),
                       Sample(False, 180, 4000, 0), Sample(True, 0, 3000, 10)):
            feed.accept(sample)
        transport = type("Transport", (), {"send": lambda self, payload: None})()
        console = Console("A", transport, "", feed)
        with ThreadingHTTPServer(("127.0.0.1", 0), make_handler(console)) as server:
            worker = threading.Thread(target=server.serve_forever)
            worker.start()
            try:
                base = f"http://127.0.0.1:{server.server_port}"
                with urlopen(base + "/api/lidar", timeout=2) as response:
                    scan = json.load(response)
                self.assertEqual(scan["status"], "ready")
                self.assertEqual(len(scan["ranges_m"]), 360)
                self.assertEqual(scan["ranges_m"][0], 3)
                self.assertIsNone(scan["ranges_m"][90])
                self.assertIsNone(scan["ranges_m"][180])
                clock.now += 1
                with urlopen(base + "/api/lidar", timeout=2) as response:
                    self.assertEqual(json.load(response)["ranges_m"], [])
                feed.disconnected(ConnectionError("test EOF"))
                with urlopen(base + "/api/lidar", timeout=2) as response:
                    self.assertEqual(json.load(response)["status"], "error")
                request = Request(base + "/api/stand", b"{}", {
                    "Content-Type": "application/json", "Origin": "http://example.invalid"})
                with self.assertRaises(HTTPError) as error:
                    urlopen(request, timeout=2)
                self.assertEqual(error.exception.code, 403)
                error.exception.close()
            finally:
                server.shutdown()
                worker.join(2)


class AutoTransportTests(unittest.TestCase):
    def test_locks_onto_first_matching_robot_only(self):
        robot = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        other = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        robot.bind(("127.0.0.1", 0))
        other.bind(("127.0.0.1", 0))
        port = robot.getsockname()[1]
        transport = AutoTransport("B", "127.0.0.1", port=port, receive_port=0)
        try:
            here = ("127.0.0.1", transport.socket.getsockname()[1])
            transport.send(b"CMD|HELLO|B|t1|0|$")
            robot.settimeout(2)
            self.assertEqual(robot.recvfrom(64)[0], b"CMD|HELLO|B|t1|0|$")
            other.sendto(tel(0, True, "boot", "t1"), here)           # 다른 포트: 무시
            robot.sendto(tel(0, True, "boot", "t1").replace(b"|B|", b"|A|", 1), here)  # 다른 ID: 무시
            robot.sendto(tel(0, True, "boot", "t1"), here)           # 맞는 로봇: 고정
            got = []
            for _ in range(50):
                got += list(transport.receive())
                if got:
                    break
                socket.socket(socket.AF_INET, socket.SOCK_DGRAM).close()
            self.assertEqual(len(got), 1)
            self.assertEqual(transport.peer, ("127.0.0.1", port))
        finally:
            transport.close()
            robot.close()
            other.close()


class RobotFilesTests(unittest.TestCase):
    def test_files_are_ascii_short_and_set_robot_id(self):
        files = render("B")
        self.assertEqual(sorted(files), sorted(n + ".py" for n in UPLOAD_ORDER))
        self.assertEqual(UPLOAD_ORDER[-1], "main")
        for name, text in files.items():
            text.encode("ascii")
            self.assertLessEqual(max(len(line) for line in text.splitlines()), 160, name)
        self.assertIn('ROBOT_ID = "B"', files["config.py"])
        with self.assertRaises(ValueError):
            render("C")

    def test_generated_files_start_latched_with_fake_modules(self):
        # 생성 파일만 sys.path 에 두고 별도 프로세스에서 시작(모듈 이름 충돌 방지)
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            for name, text in render("B").items():
                Path(folder, name).write_text(text, encoding="ascii")
            code = (
                "import sys; sys.path.insert(0, %r)\n"
                "from unittest.mock import patch\n"
                "from tests import fakes\n"
                "from tests.fakes.fake_socket import FakeNet\n"
                "from tests.fakes.fake_time import FakeClock\n"
                "fakes.install()\n"
                "with patch.dict('sys.modules', {'socket': FakeNet(), 'time': FakeClock(1000)}):\n"
                "    import main\n"
                "app = main.app\n"
                "assert app.cfg.ROBOT_ID == 'B' and app.robot.latched and app.robot.latch_reason == 'boot'\n"
                "assert app.motion.dog.last_move == (0, 0)\n"
                "app.robot.handle(b'CMD|ESTOP|B|1|$'); assert app.robot.latch_reason == 'estop'\n"
                "print('ok')\n" % folder)
            result = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, timeout=60)
            self.assertEqual(result.stdout.strip(), "ok", result.stderr)


if __name__ == "__main__":
    unittest.main()
