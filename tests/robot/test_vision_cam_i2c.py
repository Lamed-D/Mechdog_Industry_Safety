"""firmware/vision_cam/i2c_table.h 의 응답 표가 docs/protocol.md 11절과 맞는지 검사합니다.

PC에 C++ 컴파일러가 없어도 돌도록, 헤더의 표 줄을 읽어 같은 규칙을 파이썬으로 다시 계산합니다.
"""
import pathlib
import re
import unittest

HEADER = pathlib.Path(__file__).resolve().parents[2] / "firmware" / "vision_cam" / "i2c_table.h"
ROW = re.compile(r"\{(0x[0-9A-F]{2}), (0x[0-9A-F]{2}), (\d), (0x[0-9A-F]{2}), (0x[0-9A-F]{2})\}")


def table():
    return [tuple(int(v, 0) for v in m.groups()) for m in ROW.finditer(HEADER.read_text(encoding="utf-8"))]


def respond(cmd):
    for lo, hi, length, first, rest in table():
        if lo <= cmd <= hi:
            return bytes([first] + [rest] * (length - 1))
    return bytes(4)


class I2cTableTests(unittest.TestCase):
    def test_table_parsed(self):
        self.assertEqual(len(table()), 5)

    def test_command_style_reads_are_all_zero(self):
        # 명령형(0x00~0x03, 4바이트 x,y,w,h): w=0 이면 결과 없음
        for cmd in range(4):
            self.assertEqual(respond(cmd), bytes(4))

    def test_register_style_reads_mean_nothing_found(self):
        self.assertEqual(respond(0xB0), bytes(2))          # 얼굴 중심 0,0
        self.assertEqual(respond(0xC5), b"\xff" * 7)        # 색 인식: 칸 값 != 자기 번호
        for cmd in list(range(0xC0, 0xC5)) + list(range(0xA0, 0xAC)):
            self.assertEqual(respond(cmd)[0], 0xFF, hex(cmd))  # 색 번호 0(빨강)으로 오인 금지
            self.assertEqual(len(respond(cmd)), 7)

    def test_color_recognition_never_reports_a_color(self):
        data = respond(0xC5)
        self.assertFalse(any(data[i] == i for i in range(5)))

    def test_unknown_command_is_zero(self):
        self.assertEqual(respond(0x7F), bytes(4))

    def test_status_register_and_address_documented(self):
        text = HEADER.read_text(encoding="utf-8")
        self.assertIn("#define CAM_I2C_STATUS_CMD 0xE0", text)
        config = (HEADER.parent / "config.h").read_text(encoding="utf-8")
        self.assertIn("#define CAM_I2C_ADDR 0x53", config)
        self.assertIn("#define CAM_I2C_SDA 47", config)
        self.assertIn("#define CAM_I2C_SCL 48", config)


if __name__ == "__main__":
    unittest.main()
