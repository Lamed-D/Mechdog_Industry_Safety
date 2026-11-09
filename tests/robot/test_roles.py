from tests.robot.test_core import CoreTestCase


class RoleTests(CoreTestCase):
    def test_assignment_does_not_reset_or_move(self):
        self.tick()
        self.robot.handle(b"CMD|HELLO|A|b00t|0|$", PI)
        self.send("ROLE", "b00t", 1, "P", 1000)
        self.assertTrue(self.robot.latched)
        self.assertEqual(self.robot.roles.code, "P")
        self.assertIn("|1|P|1000|", self.robot.role_status())

    def test_old_session_and_term_do_not_renew(self):
        self.ready()
        self.send("ROLE", "b00t", 2, "S", 1000)
        self.tick(100)
        self.send("ROLE", "old", 3, "P", 1000)
        self.send("ROLE", "b00t", 1, "P", 1000)
        self.assertEqual((self.robot.roles.term, self.robot.roles.code), (2, "S"))
        self.assertEqual(self.robot.roles.remaining(), 900)

    def test_role_expiry_latches_even_with_ping(self):
        self.ready()
        self.send("ROLE", "b00t", 1, "P", 1000)
        self.send("MOVE", 20, 0)
        self.wait(1000)
        self.assertEqual(self.robot.roles.code, "N")
        self.assertEqual(self.robot.latch_reason, "link_lost")
        self.assertEqual(self.moves()[-1], (0, 0))

    def test_promotion_stops_and_requires_human_reset(self):
        self.ready()
        self.send("ROLE", "b00t", 1, "S", 1000)
        self.send("MOVE", 20, 0)
        self.send("ROLE", "b00t", 2, "P", 1000)
        self.assertTrue(self.robot.latched)
        self.assertEqual(self.moves()[-1], (0, 0))
        self.send("ESTOP")
        self.send("ROLE", "b00t", 3, "S", 1000)
        self.assertEqual(self.robot.latch_reason, "estop")


PI = ("127.0.0.1", 9100)
