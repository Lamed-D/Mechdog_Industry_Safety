"""Wi-Fi·UDP 링크, 라이다 중계, 전체 조립 (docs/protocol.md 1·5·6·7절)."""

import ast
import errno
import os
import unittest

from tests import fakes
from tests.fakes.fake_socket import FakeNet
from tests.fakes.fake_time import FakeClock
from tests.robot import _env

from app import App
from comm import Link
from lidar_bridge import LidarBridge

PI = ("192.168.4.10", 50000)


class AppTestCase(unittest.TestCase):
    def setUp(self):
        fakes.install()
        self.addCleanup(fakes.uninstall)
        self.cfg = _env.Cfg()
        self.clock = FakeClock(5000)
        self.net = FakeNet()
        self.dog = fakes.HW_MechDog.MechDog()
        self.imu = fakes.Hiwonder_IIC.MPU()
        self.seq = 0

    def make_app(self, ssid="test-ssid"):
        app = App(self.cfg, self.dog, fakes.Hiwonder.Battery_power, self.imu.read_angle,
                  fakes.network, self.net, fakes.machine, self.clock, ssid, "pw")
        app.start(fakes.Hiwonder.startMain)
        return app

    def wlan(self):
        return fakes.network.wlans[-1]

    def pi_send(self, text):
        return self.net.deliver_udp(self.cfg.CMD_PORT, text.encode(), PI)

    def cmd(self, name, *args):
        self.seq += 1
        self.pi_send("|".join(["CMD", name, "A", str(self.seq)] + [str(a) for a in args] + ["$"]))

    def step(self, app, ms=100):
        """10 Hz 한 주기: 시간 흐름 → 수신·텔레메트리 → 감시 → 라이다."""
        self.clock.advance(ms)
        app.comm_step()
        app.watchdog_step()
        app.lidar_step()

    def tel_lines(self):
        return [data.decode() for port, dest, data in self.net.udp_sent
                if dest == (PI[0], self.cfg.TEL_PORT)]

    def ready(self, app):
        self.step(app, 0)
        self.pi_send("CMD|HELLO|A|b00t|0|$")
        self.step(app)
        self.cmd("RESET")
        self.step(app)
        self.assertFalse(app.robot.latched, app.robot.latch_reason)


class StartTest(AppTestCase):
    def test_lock_failure_prevents_startup(self):
        from unittest.mock import patch
        with patch("_thread.allocate_lock", side_effect=RuntimeError("unavailable")):
            with self.assertRaises(RuntimeError):
                self.make_app()
        self.assertEqual(fakes.Hiwonder.main_funcs, [])

    def test_start_registers_three_loops_and_stops(self):
        self.make_app()
        self.assertEqual(len(fakes.Hiwonder.main_funcs), 3)
        self.assertEqual(self.dog.fake_calls("move"), [(0, 0)])
        self.assertTrue(self.wlan().isconnected())
        self.assertEqual(self.wlan().pm, fakes.network.WLAN.PM_NONE)

    def test_pm_not_supported_reports_warn(self):
        fakes.network.fake_set_pm_supported(False)
        app = self.make_app()
        self.ready(app)
        self.assertIn("pm_on", self.tel_lines()[-1].split("|")[12])

    def test_no_secrets_stays_latched(self):
        app = self.make_app(ssid=None)
        self.step(app)
        self.pi_send("CMD|HELLO|A|b00t|0|$")
        self.step(app)
        self.assertFalse(self.wlan().isconnected())
        self.assertTrue(app.robot.latched)
        self.assertEqual(self.net.udp_sent, [])


class FlowTest(AppTestCase):
    def test_loop_exit_stops_action_and_latches(self):
        app = self.make_app()
        self.ready(app)
        self.cmd("ACTION", "nodding_motion")
        self.step(app)

        def exit_loop(ms):
            raise KeyboardInterrupt

        self.clock.sleep_ms = exit_loop
        with self.assertRaises(KeyboardInterrupt):
            app._forever(lambda: None, 5, app.robot.fail_safe)
        self.assertIsNone(self.dog.action_running)
        self.assertTrue(app.robot.latched)
        self.assertEqual(self.dog.last_move, (0, 0))

    def test_normal_start_and_walk(self):
        app = self.make_app()
        self.ready(app)
        self.cmd("MOVE", 40, 0)
        self.step(app)
        self.assertEqual(self.dog.last_move, (40, 0))
        fields = self.tel_lines()[-1].split("|")
        self.assertEqual(fields[:2], ["TEL", "A"])
        self.assertEqual(fields[4:7], ["moving", "0", "none"])
        self.assertEqual(fields[11], "b00t")

    def test_silence_stops_within_timeout(self):
        app = self.make_app()
        self.ready(app)
        self.cmd("MOVE", 40, 0)
        self.step(app)
        for _ in range(6):
            self.step(app)  # Pi 5 가 600 ms 동안 아무것도 안 보냄
        self.step(app, 10)
        self.assertEqual(self.dog.last_move, (0, 0))
        self.assertEqual(app.robot.latch_reason, "link_lost")
        app.comm_step()  # 래치가 바뀌면 다음 수신 단계(주기 5 ms)에서 바로 보냄
        self.assertIn("|stopped|1|link_lost|", self.tel_lines()[-1])

    def test_wifi_drop_stops_and_reconnects(self):
        app = self.make_app()
        self.ready(app)
        self.cmd("MOVE", 40, 0)
        self.step(app)
        self.wlan().fake_drop()
        self.step(app, 10)
        self.assertEqual(self.dog.last_move, (0, 0))
        self.assertEqual(app.robot.latch_reason, "link_lost")
        self.assertNotIn(self.cfg.CMD_PORT, self.net.bound)  # 소켓을 닫음
        self.step(app, self.cfg.WIFI_RETRY_MS)
        self.assertTrue(self.wlan().isconnected())
        self.step(app, 10)
        self.assertIn(self.cfg.CMD_PORT, self.net.bound)  # 다시 엶
        self.cmd("MOVE", 40, 0)
        self.step(app)
        self.assertEqual(self.dog.last_move, (0, 0))  # RESET 전에는 움직이지 않음

    def test_comm_error_fails_safe(self):
        app = self.make_app()
        self.ready(app)
        self.cmd("MOVE", 40, 0)
        self.step(app)

        def broken():
            raise RuntimeError("boom")

        app.comm_step = broken
        # 루프 한 바퀴만 돌리려고 sleep 에서 멈춤
        def stop_loop(ms):
            raise KeyboardInterrupt
        self.clock.sleep_ms = stop_loop
        with self.assertRaises(KeyboardInterrupt):
            app._forever(app.comm_step, 5, app.robot.fail_safe)
        self.assertEqual(self.dog.last_move, (0, 0))
        self.assertTrue(app.robot.latched)


class LockTest(AppTestCase):
    def test_app_uses_real_lock_for_robot(self):
        app = self.make_app()
        self.assertIs(app.robot._lock, app.lock)
        self.assertTrue(hasattr(app.lock, "acquire"))  # CPython 의 _thread 잠금


class LinkTest(AppTestCase):
    def test_socket_error_reopens(self):
        link = Link(self.cfg, fakes.network, self.net, self.clock, "s", "p")
        link.start()
        link.service()
        sock = link.sock

        def bad_recv(size):
            raise OSError(errno.ECONNRESET, "reset")
        sock.recvfrom = bad_recv
        self.assertEqual(link.poll(), [])
        self.assertIsNone(link.sock)
        link.service()
        self.assertIsNotNone(link.sock)

    def test_send_failure_is_quiet(self):
        link = Link(self.cfg, fakes.network, self.net, self.clock, "s", "p")
        link.start()
        link.service()
        self.net.down = True
        self.assertFalse(link.send("TEL|A|$", (PI[0], 9101)))
        self.assertFalse(link.send("TEL|A|$", None))


class LidarBridgeTest(AppTestCase):
    def bridge(self):
        bridge = LidarBridge(self.cfg, fakes.machine, self.net)
        return bridge, fakes.machine.uarts[-1]

    def test_uart_settings_from_config(self):
        _bridge, uart = self.bridge()
        self.assertEqual((uart.uart_id, uart.baudrate, uart.rx, uart.tx, uart.rxbuf), (1, 115200, 32, 33, 4096))

    def test_backlog_warn_refreshes_and_clears_in_telemetry(self):
        app = self.make_app()
        self.ready(app)
        self.net.connect_tcp(self.cfg.LIDAR_TCP_PORT)
        app.lidar_step()
        uart = fakes.machine.uarts[-1]
        uart.fake_feed(b"x" * 3072)
        app.lidar_step()
        self.clock.advance(100)
        app.comm_step()
        self.assertIn("lidar_backlog", self.tel_lines()[-1].split("|")[12])
        self.assertEqual(app.lidar.metrics()["uart_high_water"], 3072)
        for _ in range(10):
            app.lidar_step()
        self.clock.advance(100)
        app.comm_step()
        self.assertNotIn("lidar_backlog", self.tel_lines()[-1].split("|")[12])

    def test_pending_age_wrap_and_partial_bytes_keep_order(self):
        self.clock.now_ms = (1 << 30) - 30
        bridge = LidarBridge(self.cfg, fakes.machine, self.net, self.clock)
        uart = fakes.machine.uarts[-1]
        bridge.service(True)
        client = self.net.connect_tcp(self.cfg.LIDAR_TCP_PORT)
        bridge.service(True)
        send = bridge.conn.send
        bridge.conn.send = lambda data: 0
        uart.fake_feed(b"abcdef")
        bridge.service(True)
        self.clock.advance(100)
        self.assertEqual(bridge.metrics()["pending_age_ms"], 100)
        self.assertTrue(bridge.backlogged())
        self.assertEqual(bridge.metrics()["stalls"], 1)
        bridge.conn.send = send
        bridge.service(True)
        self.assertEqual(client.recv(64), b"abcdef")
        self.assertFalse(bridge.backlogged())
        self.assertIsNone(bridge.metrics()["pending_age_ms"])

    def test_rate_and_discard_counters_do_not_invent_uart_loss(self):
        bridge = LidarBridge(self.cfg, fakes.machine, self.net, self.clock)
        uart = fakes.machine.uarts[-1]
        uart.fake_feed(b"old")
        bridge.service(True)
        client = self.net.connect_tcp(self.cfg.LIDAR_TCP_PORT)
        bridge.service(True)
        uart.fake_feed(b"x" * 512)
        client.send(b"\xa5\x20")
        self.clock.advance(1000)
        bridge.service(True)
        stats = bridge.metrics()
        self.assertEqual((stats["send_bps"], stats["receive_bps"], stats["drained"]), (512, 2, 3))
        bridge.service(False)
        self.assertFalse(bridge.backlogged())
        self.assertIsNone(bridge.metrics()["send_bps"])

    def test_two_way_relay_without_changes(self):
        bridge, uart = self.bridge()
        bridge.service(True)
        uart.fake_feed(b"\x01stale")  # 연결 전 바이트는 버림
        bridge.service(True)
        client = self.net.connect_tcp(self.cfg.LIDAR_TCP_PORT)
        bridge.service(True)
        client.send(b"\xa5\x25")
        client.send(b"\xa5\x52")
        bridge.service(True)
        self.assertEqual(uart.fake_take_tx(), b"\xa5\x25\xa5\x52")
        scan = bytes(range(256)) * 8  # 2048 바이트, 여러 번에 나눠 보냄
        uart.fake_feed(scan)
        for _ in range(10):
            bridge.service(True)
        client.settimeout(0)
        got = bytearray()
        while True:
            try:
                got.extend(client.recv(4096))
            except OSError:
                break
        self.assertEqual(bytes(got), scan)
        self.assertEqual(bridge.sent, len(scan))

    def test_partial_send_keeps_order(self):
        bridge, uart = self.bridge()
        bridge.service(True)
        client = self.net.connect_tcp(self.cfg.LIDAR_TCP_PORT)
        bridge.service(True)
        conn = bridge.conn
        real_send = conn.send
        conn.send = lambda data: real_send(data[:3])  # 한 번에 3바이트만 나감
        uart.fake_feed(b"ABCDEFGHIJ")
        for _ in range(5):
            bridge.service(True)
        self.assertEqual(client.recv(64), b"ABCDEFGHIJ")

    def test_new_client_replaces_old(self):
        bridge, uart = self.bridge()
        bridge.service(True)
        old = self.net.connect_tcp(self.cfg.LIDAR_TCP_PORT)
        bridge.service(True)
        new = self.net.connect_tcp(self.cfg.LIDAR_TCP_PORT)
        bridge.service(True)
        uart.fake_feed(b"xyz")
        bridge.service(True)
        self.assertEqual(new.recv(16), b"xyz")
        self.assertEqual(old.recv(16), b"")  # 옛 연결은 닫힘

    def test_client_close_then_wait(self):
        bridge, uart = self.bridge()
        bridge.service(True)
        client = self.net.connect_tcp(self.cfg.LIDAR_TCP_PORT)
        bridge.service(True)
        client.close()
        bridge.service(True)
        self.assertIsNone(bridge.conn)
        self.assertEqual(uart.fake_take_tx(), b"")  # 라이다에 아무것도 보내지 않음
        self.net.connect_tcp(self.cfg.LIDAR_TCP_PORT)
        bridge.service(True)
        self.assertIsNotNone(bridge.conn)

    def test_uart_failure_closes_clients_and_warns(self):
        fakes.machine.fake_fail_uart(ValueError("bad uart"))
        app = self.make_app()
        self.ready(app)
        client = self.net.connect_tcp(self.cfg.LIDAR_TCP_PORT)
        self.step(app)
        self.assertEqual(client.recv(16), b"")
        self.assertIn("lidar_uart", self.tel_lines()[-1].split("|")[12])
        self.cmd("MOVE", 40, 0)
        self.step(app)
        self.assertEqual(self.dog.last_move, (40, 0))  # 라이다 문제로 로봇을 멈추지 않음

    def connected_bridge(self):
        bridge, uart = self.bridge()
        bridge.service(True)
        client = self.net.connect_tcp(self.cfg.LIDAR_TCP_PORT)
        bridge.service(True)
        return bridge, uart, client

    def test_partial_uart_write_keeps_command_bytes(self):
        bridge, uart, client = self.connected_bridge()
        real_write = uart.write
        uart.write = lambda data: real_write(bytes(data)[:1])  # 한 번에 1바이트만 써짐
        client.send(b"\xa5\x20")
        bridge.service(True)
        self.assertEqual(uart.fake_take_tx(), b"\xa5")
        self.assertEqual(bridge.received, 1)
        client.send(b"\xa5\x25")
        bridge.service(True)
        bridge.service(True)
        bridge.service(True)
        self.assertEqual(uart.fake_take_tx(), b"\x20\xa5\x25")
        self.assertEqual(bridge.received, 4)

    def test_uart_write_none_or_zero_retries(self):
        bridge, uart, client = self.connected_bridge()
        real_write = uart.write
        answers = [None, 0]

        def flaky(data):
            if answers:
                answers.pop(0)
                return None if not answers else 0
            return real_write(data)
        uart.write = flaky
        client.send(b"\xa5\x52")
        for _ in range(3):
            bridge.service(True)
        self.assertEqual(uart.fake_take_tx(), b"\xa5\x52")

    def test_uart_write_error_drops_connection_and_buffers(self):
        bridge, uart, client = self.connected_bridge()

        def broken(data):
            raise OSError("uart")
        uart.write = broken
        client.send(b"\xa5\x20")
        bridge.service(True)
        self.assertIsNone(bridge.conn)
        self.assertEqual((bridge.pending, bridge.tx_pending), (b"", b""))

    def test_new_client_clears_unsent_bytes(self):
        bridge, uart, client = self.connected_bridge()
        uart.write = lambda data: 0
        client.send(b"\xa5\x20")
        bridge.service(True)
        self.assertEqual(bridge.tx_pending, b"\xa5\x20")
        self.net.connect_tcp(self.cfg.LIDAR_TCP_PORT)
        bridge.service(True)
        self.assertEqual(bridge.tx_pending, b"")

    def test_network_down_closes_server(self):
        bridge, _uart = self.bridge()
        bridge.service(True)
        self.assertIn(self.cfg.LIDAR_TCP_PORT, self.net.bound)
        bridge.service(False)
        self.assertNotIn(self.cfg.LIDAR_TCP_PORT, self.net.bound)


class MicroPythonSyntaxTest(unittest.TestCase):
    """장치용 파일에 MicroPython 에서 쓰기 어려운 문법·모듈이 없는지."""

    FORBIDDEN_IMPORTS = {"dataclasses", "typing", "enum", "threading", "asyncio", "pathlib"}

    def files(self):
        for folder in ("robot", "custom_sensors"):
            path = os.path.join(_env.ROOT, folder)
            for name in sorted(os.listdir(path)):
                if name.endswith(".py"):
                    yield os.path.join(path, name)

    def test_no_fstrings_or_heavy_modules(self):
        for path in self.files():
            with open(path, encoding="utf-8") as handle:
                tree = ast.parse(handle.read(), path)
            for node in ast.walk(tree):
                self.assertNotIsInstance(node, ast.JoinedStr, path)
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        self.assertNotIn(alias.name, self.FORBIDDEN_IMPORTS, path)
                if isinstance(node, ast.ImportFrom):
                    self.assertNotIn(node.module, self.FORBIDDEN_IMPORTS, path)

    def test_only_motion_moves_robot(self):
        """MechDog 동작 호출은 motion.py 와 main.py 의 시작 정지뿐."""
        moving = {"move", "action_run", "set_default_pose", "transform", "set_pose",
                  "set_gait_params", "stop_action", "set_servo", "homeostasis"}
        for path in self.files():
            base = os.path.basename(path)
            if base in ("motion.py", "main.py"):
                continue
            with open(path, encoding="utf-8") as handle:
                tree = ast.parse(handle.read(), path)
            for node in ast.walk(tree):
                if isinstance(node, ast.Attribute) and node.attr in moving:
                    owner = node.value
                    self.assertFalse(isinstance(owner, ast.Name) and owner.id in ("dog", "mechdog"),
                                     "%s: %s" % (base, node.attr))


if __name__ == "__main__":
    unittest.main()
