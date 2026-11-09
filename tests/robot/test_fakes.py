"""가짜 공식 모듈이 범위 검사·호출 기록·실패 흉내를 제대로 하는지 확인합니다."""

import errno
import sys
import unittest

from tests import fakes
from tests.fakes import FakeHardwareError
from tests.fakes.fake_socket import FakeNet
from tests.fakes.fake_time import TICKS_MAX, FakeClock


class FakesTestCase(unittest.TestCase):
    def setUp(self):
        fakes.install()
        self.addCleanup(fakes.uninstall)


class InstallTest(FakesTestCase):
    def test_official_names_importable(self):
        from HW_MechDog import MechDog
        import Hiwonder
        import Hiwonder_IIC
        import machine
        import network

        self.assertIs(MechDog, fakes.HW_MechDog.MechDog)
        self.assertIs(sys.modules["Hiwonder"], Hiwonder)
        self.assertTrue(hasattr(Hiwonder_IIC, "MPU"))
        self.assertTrue(hasattr(machine, "UART"))
        self.assertTrue(hasattr(network, "WLAN"))

    def test_uninstall_restores_modules(self):
        fakes.uninstall()
        self.assertNotIn("HW_MechDog", sys.modules)
        fakes.install()

    def test_install_resets_state(self):
        fakes.Hiwonder.fake_set_battery(6000)
        fakes.HW_MechDog.MechDog()
        fakes.install()
        self.assertEqual(fakes.Hiwonder.Battery_power(), fakes.Hiwonder.DEFAULT_BATTERY_MV)
        self.assertEqual(fakes.HW_MechDog.instances, [])


class MechDogTest(FakesTestCase):
    def setUp(self):
        super().setUp()
        from HW_MechDog import MechDog
        self.dog = MechDog()

    def test_move_records_calls(self):
        self.dog.move(40, -10)
        self.dog.move(0, 0)
        self.assertEqual(self.dog.fake_calls("move"), [(40, -10), (0, 0)])
        self.assertEqual(self.dog.last_move, (0, 0))

    def test_move_range_limits(self):
        self.dog.move(100, 30)
        self.dog.move(-100, -30)
        for step, angle in ((101, 0), (-101, 0), (0, 31), (0, -31), ("40", 0), (True, 0)):
            with self.assertRaises(FakeHardwareError, msg=(step, angle)):
                self.dog.move(step, angle)
        self.assertEqual(self.dog.last_move, (-100, -30))

    def test_action_names_only_from_doc(self):
        self.dog.action_run("sit_dowm")
        self.assertEqual(self.dog.action_running, "sit_dowm")
        for bad in ("sit_down", "dance", "", 1):
            with self.assertRaises(FakeHardwareError):
                self.dog.action_run(bad)
        self.assertEqual(len(fakes.HW_MechDog.ACTION_NAMES), 16)

    def test_action_does_not_end_by_itself_or_by_move(self):
        self.dog.action_run("nodding_motion")
        self.dog.move(0, 0)
        self.assertFalse(self.dog.action_is_over())
        self.dog.stop_action()
        self.assertTrue(self.dog.action_is_over())
        self.dog.action_run("go_prone")
        self.dog.fake_finish_action()
        self.assertTrue(self.dog.action_is_over())

    def test_set_servo_always_fails(self):
        with self.assertRaises(FakeHardwareError):
            self.dog.set_servo(9, 1500, 100)

    def test_pose_calls(self):
        self.dog.transform([0, 0, 20], [0, 0, 0], 1000)
        self.dog.set_pose([0, 0, 0], [0, 20, 0], 300)
        self.dog.set_default_pose()
        self.dog.set_gait_params(150, 500, 40)
        self.assertEqual(self.dog.fake_calls("transform"), [([0, 0, 20], [0, 0, 0], 1000)])
        with self.assertRaises(FakeHardwareError):
            self.dog.transform([0, 0], [0, 0, 0], 1000)
        for bad in (float("nan"), float("inf"), -float("inf")):
            with self.assertRaises(FakeHardwareError):
                self.dog.transform([bad, 0, 0], [0, 0, 0], 1000)
            with self.assertRaises(FakeHardwareError):
                self.dog.set_pose([0, 0, 0], [0, bad, 0], 300)
            with self.assertRaises(FakeHardwareError):
                self.dog.move(bad, 0)
        with self.assertRaises(FakeHardwareError):
            self.dog.set_pose([0, 0, 0], [0, 0, 0], -1)
        with self.assertRaises(FakeHardwareError):
            self.dog.set_gait_params(0, 500, 40)

    def test_homeostasis_and_tip_over(self):
        self.dog.homeostasis(True)
        self.assertTrue(self.dog.read_homeostasis_status())
        self.dog.fake_tip_over()
        self.assertFalse(self.dog.read_homeostasis_status())
        with self.assertRaises(FakeHardwareError):
            self.dog.homeostasis(1)


class HiwonderTest(FakesTestCase):
    def test_start_main_registers_without_running(self):
        import Hiwonder
        ran = []
        Hiwonder.startMain(lambda: ran.append(1))
        self.assertEqual(ran, [])
        Hiwonder.main_funcs[0]()
        self.assertEqual(ran, [1])

    def test_battery_values_and_failures(self):
        import Hiwonder
        self.assertEqual(Hiwonder.Battery_power(), 7800)
        Hiwonder.fake_set_battery(None)
        self.assertIsNone(Hiwonder.Battery_power())
        Hiwonder.fake_set_battery(OSError("i2c"))
        with self.assertRaises(OSError):
            Hiwonder.Battery_power()

    def test_buzzer_and_button(self):
        import Hiwonder
        Hiwonder.Buzzer().playTone(800, 100, True)
        with self.assertRaises(FakeHardwareError):
            Hiwonder.Buzzer().playTone(800, 100, 1)
        pressed = []
        button = Hiwonder.Button(1)
        button.Clicked(lambda: pressed.append(1))
        button.fake_click()
        self.assertEqual(pressed, [1])


class HiwonderIICTest(FakesTestCase):
    def test_mpu_read_angle_and_failure(self):
        import Hiwonder_IIC
        imu = Hiwonder_IIC.MPU(Hiwonder_IIC.IIC(1))
        Hiwonder_IIC.fake_set_angle([1.5, -0.5])
        self.assertEqual(imu.read_angle(), [1.5, -0.5])
        Hiwonder_IIC.fake_set_angle(None)
        self.assertIsNone(imu.read_angle())
        Hiwonder_IIC.fake_set_angle(OSError("i2c"))
        with self.assertRaises(OSError):
            imu.read_angle()

    def test_sonar(self):
        import Hiwonder_IIC
        sonar = Hiwonder_IIC.I2CSonar(Hiwonder_IIC.IIC(1))
        Hiwonder_IIC.fake_set_distance(42)
        self.assertEqual(sonar.getDistance(), 42)
        with self.assertRaises(FakeHardwareError):
            sonar.setRGB(0, 256, 0, 0)
        with self.assertRaises(FakeHardwareError):
            Hiwonder_IIC.IIC(3)


class MachineTest(FakesTestCase):
    def test_uart_feed_read_and_overflow(self):
        import machine
        uart = machine.UART(1, baudrate=115200, rx=32, tx=33, rxbuf=8)
        self.assertIsNone(uart.read())
        uart.fake_feed(b"\xa5\x5a\x01\x02\x03\x04\x05\x06\x07\x08")
        self.assertEqual(uart.any(), 8)
        self.assertEqual(uart.dropped, 2)
        self.assertEqual(uart.read(3), b"\xa5\x5a\x01")
        buf = bytearray(10)
        self.assertEqual(uart.readinto(buf), 5)
        self.assertEqual(bytes(buf[:5]), b"\x02\x03\x04\x05\x06")

    def test_uart_write_and_loopback(self):
        import machine
        uart = machine.UART(1, baudrate=115200)
        self.assertEqual(uart.write(b"\xa5\x50"), 2)
        self.assertEqual(uart.fake_take_tx(), b"\xa5\x50")
        self.assertIsNone(uart.read())
        uart.loopback = True
        uart.write(b"\xa5\x52")
        self.assertEqual(uart.read(), b"\xa5\x52")

    def test_uart_open_failure(self):
        import machine
        machine.fake_fail_uart(ValueError("invalid UART"))
        with self.assertRaises(ValueError):
            machine.UART(1, baudrate=115200, rx=32, tx=33, rxbuf=4096)
        machine.fake_fail_uart(None)
        machine.UART(1, baudrate=115200)

    def test_unique_id_and_pin(self):
        import machine
        self.assertEqual(len(machine.unique_id()), 6)
        pin = machine.Pin(4, machine.Pin.IN)
        pin.value(1)
        self.assertEqual(pin.value(), 1)


class NetworkTest(FakesTestCase):
    def test_connect_and_drop(self):
        import network
        wlan = network.WLAN(network.STA_IF)
        with self.assertRaises(OSError):
            wlan.connect("ssid", "pw")
        wlan.active(True)
        wlan.connect("ssid", "pw")
        self.assertTrue(wlan.isconnected())
        self.assertEqual(wlan.ifconfig()[0], network.FAKE_IP)
        wlan.fake_drop()
        self.assertFalse(wlan.isconnected())
        self.assertNotIn("pw", repr(network.calls))

    def test_no_access_point(self):
        import network
        network.fake_set_ap(False)
        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)
        wlan.connect("ssid", "pw")
        self.assertFalse(wlan.isconnected())

    def test_power_save_support_switch(self):
        import network
        wlan = network.WLAN(network.STA_IF)
        wlan.config(pm=network.WLAN.PM_NONE)
        self.assertEqual(wlan.pm, 0)
        network.fake_set_pm_supported(False)
        self.assertFalse(hasattr(network.WLAN, "PM_NONE"))
        with self.assertRaises(ValueError):
            wlan.config(pm=0)
        fakes.reset()
        self.assertTrue(hasattr(network.WLAN, "PM_NONE"))


class FakeClockTest(unittest.TestCase):
    def test_sleep_advances(self):
        clock = FakeClock()
        start = clock.ticks_ms()
        clock.sleep_ms(600)
        clock.sleep(0.05)
        self.assertEqual(clock.ticks_diff(clock.ticks_ms(), start), 650)
        self.assertEqual(clock.sleeps, [600, 50.0])

    def test_ticks_wrap(self):
        clock = FakeClock(start_ms=TICKS_MAX - 100)
        start = clock.ticks_ms()
        clock.advance(300)
        now = clock.ticks_ms()
        self.assertLess(now, start)  # 넘쳐서 0 근처로 돌아옴
        self.assertEqual(clock.ticks_diff(now, start), 300)
        self.assertEqual(clock.ticks_diff(start, now), -300)
        self.assertEqual(clock.ticks_add(start, 300), now)


class FakeNetTest(unittest.TestCase):
    def test_udp_roundtrip(self):
        net = FakeNet()
        sock = net.socket(net.AF_INET, net.SOCK_DGRAM)
        sock.setsockopt(net.SOL_SOCKET, net.SO_REUSEADDR, 1)
        sock.bind(("0.0.0.0", 9100))
        sock.settimeout(0)
        with self.assertRaises(OSError) as ctx:
            sock.recvfrom(64)
        self.assertEqual(ctx.exception.errno, errno.EAGAIN)
        self.assertTrue(net.deliver_udp(9100, b"CMD|PING|A|1|$"))
        self.assertFalse(net.deliver_udp(9999, b"x"))
        data, addr = sock.recvfrom(64)
        self.assertEqual(data, b"CMD|PING|A|1|$")
        sock.sendto(b"TEL|A|0|$", (addr[0], 9101))
        self.assertEqual(net.udp_sent, [(9100, (addr[0], 9101), b"TEL|A|0|$")])

    def test_udp_send_fails_when_down(self):
        net = FakeNet()
        sock = net.socket(net.AF_INET, net.SOCK_DGRAM)
        net.down = True
        with self.assertRaises(OSError):
            sock.sendto(b"x", ("192.168.4.10", 9101))

    def test_bind_twice_fails(self):
        net = FakeNet()
        net.socket(net.AF_INET, net.SOCK_DGRAM).bind(("0.0.0.0", 9100))
        with self.assertRaises(OSError):
            net.socket(net.AF_INET, net.SOCK_DGRAM).bind(("0.0.0.0", 9100))

    def test_tcp_server_two_way_and_close(self):
        net = FakeNet()
        server = net.socket(net.AF_INET, net.SOCK_STREAM)
        server.bind(("0.0.0.0", 20108))
        with self.assertRaises(OSError):
            net.connect_tcp(20108)  # listen 전
        server.listen(1)
        server.settimeout(0)
        client = net.connect_tcp(20108)
        conn, _addr = server.accept()
        client.send(b"\xa5\x50")
        self.assertEqual(conn.recv(16), b"\xa5\x50")
        conn.sendall(b"\xa5\x5a\x14")
        self.assertEqual(client.recv(16), b"\xa5\x5a\x14")
        conn.settimeout(0)
        with self.assertRaises(OSError):
            conn.recv(16)  # 아직 보낸 것 없음
        client.close()
        self.assertEqual(conn.recv(16), b"")
        with self.assertRaises(OSError):
            conn.send(b"x")


if __name__ == "__main__":
    unittest.main()
