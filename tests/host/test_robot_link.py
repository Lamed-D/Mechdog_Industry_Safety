import unittest
from host.robot_link import RobotLink, parse_telemetry


def tel(seq=1, *, state="idle", latch=0, reason="none", boot="b1", battery="7800", tilt="0.0", uptime=100):
    return (f"TEL|A|{seq}|0|{state}|{latch}|{reason}|{battery}|{tilt}|0.0|{uptime}|{boot}|none|$").encode()


class LinkTests(unittest.TestCase):
    def test_fresh_telemetry_without_ack_progress_latches_estop(self):
        self.link.observe(tel())
        self.link.step()
        for seq in range(2, 10):
            self.now += 0.11
            self.link.observe(tel(seq, uptime=seq * 100))
            self.link.mark_scan(True)
            self.link.move(40, 0)
            self.link.step()
        self.assertTrue(self.link.emergency)
        self.assertIn(b"ESTOP", self.sent[-1])

    def test_stale_link_does_not_resume_when_telemetry_returns(self):
        self.link.observe(tel())
        self.link.step()
        self.tick(0.41)
        self.link.observe(tel(2, uptime=500))
        self.link.mark_scan(True)
        self.link.move(40, 0)
        self.assertIn(b"ESTOP", self.tick())

    def test_ack_progress_allows_healthy_commands(self):
        self.link.observe(tel())
        for seq in range(2, 20):
            self.now += 0.11
            data = tel(seq, uptime=seq * 100).replace(b"|0|idle|", ("|%d|idle|" % self.link.seq).encode())
            self.link.observe(data)
            self.link.mark_scan(True)
            self.link.move(40, 0)
            self.link.step()
        self.assertFalse(self.link.emergency)
        self.assertIn(b"MOVE", self.sent[-1])

    def test_future_ack_does_not_refresh_link(self):
        self.link.observe(tel())
        self.now = 0.2
        data = tel(2).replace(b"|0|idle|", b"|999|idle|")
        self.assertFalse(self.link.observe(data))
        self.assertEqual(self.link.last_seen, 0.0)

    def test_stale_gap_detected_even_before_scheduler_step(self):
        self.link.observe(tel())
        self.now = 0.5
        self.link.observe(tel(2, uptime=600))
        self.assertTrue(self.link.emergency)

    def test_fault_estop_keeps_send_rate_bounded(self):
        self.link.observe(tel())
        self.tick(0.5)
        self.link.step()  # 첫 ESTOP은 즉시 허용
        count = len(self.sent)
        for _ in range(10):
            self.now += 0.001
            self.link.step()
        self.assertEqual(len(self.sent), count)

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
