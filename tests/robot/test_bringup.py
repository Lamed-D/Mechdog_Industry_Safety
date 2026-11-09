"""tools/bringup/ 스크립트를 가짜 모듈로 돌려 봅니다(문법·해석·실패 표시)."""

import contextlib
import importlib.util
import io
import os
import unittest

from tests import fakes
from tests.fakes.fake_time import FakeClock

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def load(name):
    path = os.path.join(ROOT, "tools", "bringup", name + ".py")
    spec = importlib.util.spec_from_file_location("bringup_" + name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeLidarUart:
    """명령에 응답하는 가짜 라이다 UART."""

    def __init__(self, *args, **kwargs):
        self.rx = bytearray()

    def any(self):
        return len(self.rx)

    def read(self, n=None):
        if not self.rx:
            return None
        n = len(self.rx) if n is None else n
        data = bytes(self.rx[:n])
        del self.rx[:n]
        return data

    def write(self, data):
        if data == b"\xa5\x52":
            self.rx.extend(b"\xa5\x5a\x03\x00\x00\x00\x06" + b"\x00\x00\x00")
        elif data == b"\xa5\x50":
            self.rx.extend(b"\xa5\x5a\x14\x00\x00\x00\x04" + bytes([0x18, 0x1d, 0x01, 0x07]) + bytes(range(16)))
        return len(data)


class BringupTest(unittest.TestCase):
    def test_standalone_vision_probe_success_and_failure_without_motion(self):
        module = load("vision_probe")
        clock = FakeClock()
        fakes.Hiwonder_IIC.fake_set_face(True)
        result = module.run(fakes.Hiwonder_IIC, clock)
        self.assertEqual(result["status"], "observed")
        self.assertEqual(result["fallen_person"], "unknown")
        fakes.Hiwonder_IIC.fake_set_face(OSError(5))
        failure = module.run(fakes.Hiwonder_IIC, clock)
        self.assertEqual(failure["status"], "unknown")
        self.assertEqual((failure["stage"], failure["errno"]), ("face_read", 5))
        self.assertEqual(fakes.HW_MechDog.instances, [])
        self.assertEqual(fakes.machine.uarts, [])

    def test_vision_probe_distinguishes_bus_and_camera_init_failures(self):
        module = load("vision_probe")
        class Broken:
            @staticmethod
            def IIC(bus):
                raise OSError(19)
            @staticmethod
            def ESP32S3Cam(bus):
                raise OSError(5)
        result = module.run(Broken, FakeClock())
        self.assertEqual((result["stage"], result["errno"]), ("iic_init", 19))
        Broken.IIC = staticmethod(lambda bus: object())
        result = module.run(Broken, FakeClock())
        self.assertEqual((result["stage"], result["errno"]), ("camera_init", 5))

    def test_mechdog_only_does_not_construct_robot_or_open_uart(self):
        result = load("mechdog_only").main()
        self.assertEqual(result["battery_mv"], 7800)
        self.assertTrue(all(result["api"].values()))
        self.assertEqual(fakes.HW_MechDog.instances, [])
        self.assertEqual(fakes.machine.uarts, [])

    def setUp(self):
        fakes.install()
        self.addCleanup(fakes.uninstall)
        quiet = contextlib.redirect_stdout(io.StringIO())  # 스크립트 출력은 시험 결과에 섞지 않음
        quiet.__enter__()
        self.addCleanup(quiet.__exit__, None, None, None)

    def with_clock(self, module):
        module.time = FakeClock()
        return module

    def test_board_info_reports_ok_and_fail(self):
        module = load("b1_board_info")
        self.assertTrue(module.check("x", lambda: 1))
        self.assertFalse(module.check("y", lambda: 1 / 0))
        fakes.network.fake_set_pm_supported(False)
        module.main()  # 가짜 모듈에서 예외 없이 끝까지 돔
        self.assertEqual(fakes.HW_MechDog.instances, [])  # MechDog 를 만들지 않음

    def test_loopback(self):
        module = self.with_clock(load("b2_uart_loopback"))
        original = fakes.machine.UART

        def looped(*args, **kwargs):
            uart = original(*args, **kwargs)
            uart.loopback = True
            return uart
        fakes.machine.UART = looped
        self.addCleanup(setattr, fakes.machine, "UART", original)
        self.assertTrue(module.main())

    def test_loopback_fails_without_jumper(self):
        module = self.with_clock(load("b2_uart_loopback"))
        self.assertFalse(module.main())

    def test_lidar_info(self):
        module = self.with_clock(load("b3_lidar_info"))
        self.addCleanup(setattr, fakes.machine, "UART", fakes.machine.UART)
        fakes.machine.UART = FakeLidarUart
        self.assertTrue(module.main())
        self.assertEqual(module.parse_health(b"\x02\x05\x01"), ("Error", 0x105))
        info = module.parse_info(bytes([0x18, 0x1d, 0x01, 0x07]) + bytes(range(16)))
        self.assertEqual(info["firmware"], "1.29")
        self.assertEqual(info["serial"][:4], "0001")

    def test_lidar_no_answer(self):
        module = self.with_clock(load("b3_lidar_info"))
        self.assertFalse(module.main())  # 응답 없음 → 시간 제한 후 실패로 끝남

    def test_rtt_summary(self):
        module = load("rtt_probe")
        result = module.summarize([10.0, 20.0, 30.0, 400.0], sent=5, gaps_ms=[100, 700, 90])
        self.assertEqual(result["lost"], 1)
        self.assertEqual(result["p50_ms"], 30.0)
        self.assertEqual(result["max_ms"], 400.0)
        self.assertEqual(result["gaps_over_timeout"], 1)
        self.assertIsNone(module.summarize([], 3, [])["p99_ms"])

    def test_camera_frame_count_across_chunks(self):
        module = load("camera_check")
        data = b"xx\xff\xd8aaaa\xff" + b"\xd8bb" + b"\xff\xd8"
        total, frames = module.count_frames(io.BytesIO(data), seconds=5, chunk=7)
        self.assertEqual((total, frames), (len(data), 3))


if __name__ == "__main__":
    unittest.main()
