"""명령 메시지 해석 (docs/protocol.md 2·3·4.4절)."""

import unittest

from tests.robot import _env  # noqa: F401

import proto


def p(text, robot_id="A"):
    data = text.encode() if isinstance(text, str) else text
    return proto.parse(data, robot_id)


class ParseTest(unittest.TestCase):
    def test_valid_commands(self):
        kind, cmd = p("CMD|MOVE|A|3381|40|-10|$")
        self.assertEqual((kind, cmd.name, cmd.seq, cmd.args), (proto.OK, "MOVE", 3381, [40, -10]))
        kind, cmd = p("CMD|ACTION|A|17|nodding_motion|$\r\n")
        self.assertEqual((kind, cmd.args), (proto.OK, ["nodding_motion"]))
        kind, cmd = p("CMD|POSE|A|5|prone|$")
        self.assertEqual(cmd.args, ["prone"])
        for name in ("STOP", "ESTOP", "RESET", "PING"):
            kind, cmd = p("CMD|%s|A|9|$" % name)
            self.assertEqual((kind, cmd.name, cmd.seq), (proto.OK, name, 9))

    def test_bytes_around_message_ignored(self):
        kind, cmd = p(b"\x00junkCMD|PING|A|1|$tail")
        self.assertEqual((kind, cmd.name), (proto.OK, "PING"))

    def test_hello(self):
        kind, cmd = p("CMD|HELLO|A|6f3a91|0|$")
        self.assertEqual((kind, cmd.seq, cmd.args), (proto.OK, "6f3a91", [0]))
        self.assertEqual(p("CMD|HELLO|A|6f3a91|1|$")[1].args, [1])  # 버전 판단은 core
        self.assertEqual(p("CMD|HELLO|A|0123456789abcdefX|0|$")[0], proto.BAD)  # 17자
        self.assertEqual(p("CMD|HELLO|A|ab-c|0|$")[0], proto.BAD)

    def test_all_robots_only_for_stop(self):
        self.assertEqual(p("CMD|ESTOP|*|902|$")[0], proto.OK)
        self.assertTrue(p("CMD|STOP|*|5|$")[1].to_all)
        self.assertEqual(p("CMD|MOVE|*|5|10|0|$")[0], proto.BAD)
        self.assertEqual(p("CMD|HELLO|*|abc|0|$")[0], proto.BAD)

    def test_other_robot_ignored(self):
        self.assertEqual(p("CMD|MOVE|B|1|40|0|$"), (proto.OTHER, None))
        self.assertEqual(p("CMD|NONSENSE|B|x|$")[0], proto.OTHER)

    def test_garbage(self):
        for text in (b"", b"hello", b"CMD|MOVE|A|1|40|0", b"MOVE|A|1|$", b"CMD|STOP|$", b"CMD|$"):
            self.assertEqual(p(text)[0], proto.GARBAGE, text)

    def test_bad_for_me(self):
        cases = [
            "CMD|JUMP|A|1|$",            # 모르는 이름
            "CMD|MOVE|A|1|40|$",         # 필드 개수
            "CMD|MOVE|A|1|40|0|0|$",
            "CMD|MOVE|A|1|12.5|0|$",     # 정수 아님
            "CMD|MOVE|A|1|+5|0|$",
            "CMD|MOVE|A|1||0|$",
            "CMD|MOVE|A|-1|5|0|$",       # 음수 seq
            "CMD|MOVE|A|2147483648|5|0|$",
            "CMD|ACTION|A|1|boxing|$",   # 허용 목록 밖
            "CMD|ACTION|A|1|sit_down|$",
            "CMD|POSE|A|1|stand|$",
            "CMD|PING|A|1 |$",           # 공백
            "CMD|PING|A|abc|$",
        ]
        for text in cases:
            self.assertEqual(p(text)[0], proto.BAD, text)

    def test_length_and_ascii(self):
        long = "CMD|PING|A|" + "1" * 60 + "|$"
        self.assertGreater(len(long), proto.MAX_CMD_LEN)
        self.assertEqual(p(long)[0], proto.BAD)
        self.assertEqual(p("CMD|ACTION|A|1|sit_dowm\xe9|$".encode("latin-1"))[0], proto.BAD)

    def test_parse_int(self):
        self.assertEqual(proto.parse_int("-12"), -12)
        for text in ("", "-", "+1", "1.0", " 1", "1e3", "１"):
            self.assertIsNone(proto.parse_int(text), text)


if __name__ == "__main__":
    unittest.main()
