import unittest

from host.robot_link import RobotLink
from host.roles import RoleCoordinator, parse_role_status
from tests import fakes
from tests.fakes.fake_time import FakeClock
from tests.robot import _env
import core
from motion import Motion


class RoleIntegrationTests(unittest.TestCase):
    def setUp(self):
        fakes.install()
        self.addCleanup(fakes.uninstall)
        self.clock = FakeClock(1000)
        self.boards, self.links = {}, {}
        self.sent = []
        for robot in ("A", "B"):
            cfg = _env.Cfg()
            cfg.ROBOT_ID = robot
            board = core.Robot(cfg, Motion(fakes.HW_MechDog.MechDog()), self.clock,
                               lambda: 7800, lambda: (0, 0))
            self.boards[robot] = board

            def send(payload, board=board):
                self.sent.append(payload)
                board.handle(payload)

            self.links[robot] = RobotLink(robot, send, clock=lambda: self.clock.ticks_ms() / 1000,
                                         boot_id=robot + "host")
        self.coordinator = RoleCoordinator(self.links)
        self.round()
        self.round()

    def round(self, online=("A", "B")):
        self.clock.advance(110)
        for robot, board in self.boards.items():
            board.tick(True)
            if robot in online:
                self.links[robot].observe(board.telemetry().encode())
                status = board.role_status()
                if status:
                    self.links[robot].observe(status.encode())
        self.coordinator.step()
        for link in self.links.values():
            link.step()

    def test_acknowledged_roles_failover_without_moving(self):
        self.round()
        self.assertEqual(self.coordinator.active_primary(), "A")
        self.assertEqual(self.links["B"].confirmed_role(), "secondary")
        for _ in range(7):
            self.round(online=("B",))
        self.assertEqual(self.coordinator.active_primary(), "B")
        self.assertTrue(self.boards["B"].latched)
        self.assertEqual(self.boards["B"].latch_reason, "link_lost")
        self.round()
        self.assertEqual(self.coordinator.primary, "B")
        self.assertTrue(all(b"|MOVE|" not in p and b"|RESET|" not in p for p in self.sent))

    def test_replayed_and_wrong_session_ack_do_not_confirm(self):
        self.round()
        link = self.links["A"]
        status = self.boards["A"].role_status().encode()
        self.assertFalse(link.observe(status))
        self.assertFalse(link.observe(status.replace(b"Ahost", b"wrong")))
        with self.assertRaises(ValueError):
            parse_role_status(b"ROLE|A|Ahost|1|P|9999|1|$")

    def test_wire_length_and_lease_limits(self):
        link = self.links["A"]
        link.seq = 2147483646
        payload = link._command("ROLE", "1234567890abcdef", 2147483647, "S", 1000)
        self.assertLessEqual(len(payload), 64)
        self.boards["A"].handle(b"CMD|ROLE|A|99|Ahost|1|P|9999|$")
        self.assertTrue(self.boards["A"].latched)
