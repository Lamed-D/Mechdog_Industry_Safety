import unittest
from host.robot_link import RobotLink, parse_telemetry


def tel(seq=1, *, state="idle", latch=0, reason="none", boot="b1", battery="7800", tilt="0.0", uptime=100):
    return (f"TEL|A|{seq}|0|{state}|{latch}|{reason}|{battery}|{tilt}|0.0|{uptime}|{boot}|none|$").encode()


class LinkTests(unittest.TestCase):
    def setUp(self):
        self.now = 0.0
        self.sent = []
        self.link = RobotLink("A", self.sent.append, clock=lambda: self.now, boot_id="b1")

    def tick(self, seconds=0.11):
        self.now += seconds
        self.link.step()
        return self.sent[-1]

    def test_handshake_and_exact_wire_format(self):
        self.assertEqual(self.tick(), b"CMD|HELLO|A|b1|0|$")
        self.link.observe(tel())
        self.assertEqual(self.tick(), b"CMD|STOP|A|1|$")
        self.link.mark_scan(True)
        self.link.move(40, -10)
        self.assertEqual(self.tick(), b"CMD|MOVE|A|2|40|-10|$")

    def test_old_and_other_session_telemetry_does_not_refresh(self):
        self.link.observe(tel())
        self.now = 0.3
        self.assertFalse(self.link.observe(tel()))
        self.now = 0.5
        self.assertFalse(self.link.fresh())
        self.assertFalse(self.link.observe(tel(2, boot="old")))
        self.assertIsNone(self.link.latest)

    def test_scan_loss_and_intent_expiry_stop(self):
        self.link.observe(tel())
        self.link.move(40, 0)
        self.assertIn(b"STOP", self.tick())
        self.link.move(40, 0)
        self.link.mark_scan(True)
        self.assertIn(b"MOVE", self.tick())
        self.link.mark_scan(False)
        self.assertIn(b"STOP", self.tick())

    def test_estop_is_sticky_and_reset_is_explicit(self):
        self.link.estop()
        self.assertIn(b"ESTOP", self.tick())
        with self.assertRaises(ValueError):
            self.link.request_reset()
        self.link.observe(tel(state="stopped", latch=1, reason="estop"))
        self.link.request_reset()
        self.assertIn(b"RESET", self.tick())
        self.assertIn(b"PING", self.tick())

    def test_invalid_sensor_and_state_rejected(self):
        for data in (tel(tilt="nan"), tel(battery="0"), tel(latch=1), b"bad"):
            with self.assertRaises(ValueError):
                parse_telemetry(data)

    def test_send_failure_discards_motion(self):
        self.link.observe(tel())
        self.link.move(40, 0)
        def fail(data):
            raise OSError("disconnected")
        self.link.send = fail
        with self.assertRaises(OSError):
            self.link.step()
        self.assertIsNone(self.link.intent)
        self.assertEqual(self.link.status(), "unknown")
