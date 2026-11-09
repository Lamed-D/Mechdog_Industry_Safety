"""firmware/vision_cam/i2c_table.h 의 고정 응답이 docs/protocol.md 11.2절의 모든 읽기 형식에서
"결과 없음"으로 읽히는지 검사합니다. PC에 C++ 컴파일러가 없어도 돌도록 헤더의 배열 값을 읽습니다.

응답은 명령과 무관하게 같으므로, 반복 시작 읽기에서 직전 명령 기준으로 답해도 결과가 같습니다.
"""
import pathlib
import re
import unittest

FW = pathlib.Path(__file__).resolve().parents[2] / "firmware" / "vision_cam"


def reply(name):
    text = (FW / "i2c_table.h").read_text(encoding="utf-8")
    body = re.search(r"%s\[CAM_I2C_REPLY_LEN\] = \{([^}]*)\}" % name, text).group(1)
    return bytes(int(v, 0) for v in body.split(","))


# 메인 보드 쪽 해석(제조사 형식 기준). True = "인식됨"
def face_center(data):            # 0xB0, 2바이트: 둘 다 0 이 아니면 얼굴
    return data[0] != 0 and data[1] != 0


def color_recognition(data):      # 0xC5, 7바이트 중 0~4번 칸: 칸 값이 자기 번호면 그 색
    return any(data[i] == i for i in range(5))


def follow_or_line(data):         # 0xC0~0xC4, 0xA0~0xAB: 첫 바이트가 색 번호(0~4)면 인식
    return data[0] <= 4


def command_box(data):            # 0x52 명령형 4바이트 x,y,w,h: w > 0 이면 결과
    return data[2] > 0


def command_any(data):            # 0x52 명령형을 "0 이 아닌 값이 있으면 결과"로 읽는 경우
    return any(data[:4])


class I2cReplyTests(unittest.TestCase):
    def test_register_style_reply_means_nothing_found_in_every_format(self):
        data = reply("CAM_I2C_REPLY_REGISTER")
        self.assertEqual(len(data), 7)
        for reader in (face_center, color_recognition, follow_or_line, command_box):
            self.assertFalse(reader(data[:2] if reader is face_center else data), reader.__name__)

    def test_command_style_reply_is_all_zero(self):
        data = reply("CAM_I2C_REPLY_COMMAND")
        self.assertEqual(data, bytes(7))
        for reader in (face_center, command_box, command_any):
            self.assertFalse(reader(data), reader.__name__)

    def test_reply_does_not_depend_on_command(self):
        source = (FW / "i2c_compat.cpp").read_text(encoding="utf-8")
        self.assertIn("cam_i2c_reply(CAM_I2C_ADDR)", source)
        self.assertNotIn("s_cmd", source)

    def test_address_and_pins(self):
        config = (FW / "config.h").read_text(encoding="utf-8")
        for line in ("#define CAM_I2C_ADDR 0x53", "#define CAM_I2C_SDA 47", "#define CAM_I2C_SCL 48"):
            self.assertIn(line, config)


if __name__ == "__main__":
    unittest.main()
