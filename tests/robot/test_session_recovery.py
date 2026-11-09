import unittest

from host.robot_link import RobotLink
from tests import fakes
from tests.fakes.fake_time import FakeClock
from tests.robot import _env
import core
from motion import Motion


class SessionRecoveryTests(unittest.TestCase):
    def setUp(self):
        fakes.install()
        self.addCleanup(fakes.uninstall)
        self.clock = FakeClock(1000)
        self.sent = []
        self.new_board()

        def send(payload):
            self.sent.append(payload)
            self.board.handle(payload, ("127.0.0.1", 9100))
        self.link = RobotLink("A", send, boot_id="host1", require_scan=False,
                              clock=lambda: self.clock.ticks_ms() / 1000)

    def new_board(self):
        self.board = core.Robot(_env.Cfg(), Motion(fakes.HW_MechDog.MechDog()), self.clock,
                                lambda: 7800, lambda: (0, 0))

    def report(self):
        self.board.tick(True)
        if self.board.telemetry_dest() is not None:
            return self.link.observe(self.board.telemetry().encode())
        return False

    def test_first_estop_can_observe_latch_and_accept_only_human_reset(self):
        self.link.estop()
        self.link.step()
        self.assertIn(b"|ESTOP|", self.sent[0])
        self.assertTrue(self.report())
        self.assertTrue(self.link.fresh())
        self.assertEqual(self.board.latch_reason, "estop")
        self.assertFalse(any(b"|RESET|" in p for p in self.sent))
        self.link.request_reset()
        self.link.step()
        self.assertFalse(self.board.latched)
        self.assertFalse(any(b"|MOVE|" in p for p in self.sent))

    def test_same_host_robot_reboot_recovers_fresh_telemetry_under_estop(self):
        self.link.step()
        self.clock.advance(100)
        self.report()
        self.link.request_reset()
        self.link.step()
        self.clock.advance(100)
        self.report()
        self.link.move(20, 0)
        self.clock.advance(110)
        self.link.step()
        self.report()
        old_session = self.link.boot_id
        self.new_board()
        self.board.handle(("CMD|HELLO|A|%s|0|$" % old_session).encode(), ("127.0.0.1", 9100))
        before = len(self.sent)
        self.assertFalse(self.report())
        self.assertNotEqual(self.link.boot_id, old_session)
        self.link.step()
        self.assertTrue(self.report())
        self.assertTrue(self.link.fresh() and self.link.emergency and self.board.latched)
        self.assertFalse(any(b"|MOVE|" in p or b"|RESET|" in p for p in self.sent[before:]))
