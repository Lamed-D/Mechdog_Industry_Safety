import unittest

from scenario import Command, Notice, Scenario, Timeouts


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def fall(robot="A", status="suspected_fall", confidence=0.9):
    return {"robot": robot, "status": status, "confidence": confidence, "source": "synthetic",
            "duration_s": 2.0, "threshold": 0.8, "hold_s": 2.0}


def commands(out):
    return [(c.robot, c.kind, c.arg) for c in out if isinstance(c, Command)]


def notices(out, kind=None):
    return [n for n in out if isinstance(n, Notice) and (kind is None or n.kind == kind)]


class ScenarioTestBase(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.s = Scenario(clock=self.clock, timeouts=Timeouts(dispatch_s=10, guide_s=20, return_s=15, remind_s=5))
        self.s.robot_ready("A")
        self.s.robot_ready("B")
        self.s.start_patrol()

    def to_phase(self, phase):
        s = self.s
        s.detection(fall("A"))
        if phase == "dispatch":
            return
        s.arrived("B", "manager")
        if phase == "at_manager":
            return
        s.start_guide()
        if phase == "guiding":
            return
        s.arrived("B", "site")


class HappyPathTests(ScenarioTestBase):
    def test_vision_loss_stops_dispatch_and_guiding_until_human_retry(self):
        for phase in ("dispatch", "guiding"):
            with self.subTest(phase=phase):
                self.setUp()
                self.to_phase(phase)
                out = self.s.detection(fall("B", status="unknown"))
                self.assertIn(("B", "stop", None), commands(out))
                self.assertEqual(self.s.phase, "suspended")
                self.assertFalse(commands(self.s.retry()))
                self.assertFalse(commands(self.s.detection(fall("B", status="unconfirmed"))))
                self.assertEqual(self.s.phase, "suspended")
                self.assertTrue(commands(self.s.retry()))

    def test_unknown_camera_blocks_new_patrol_until_valid_evidence(self):
        self.s.detection(fall("A", status="unknown"))
        out = self.s.start_patrol()
        self.assertNotIn(("A", "patrol", None), commands(out))

    def test_full_demo_flow(self):
        s = self.s
        self.assertEqual(s.phase, "patrol")
        out = s.detection(fall("A"), zone="Z1")
        self.assertEqual(commands(out), [("A", "stop", None), ("A", "action", "nodding_motion"),
                                         ("B", "goto", "manager")])
        alert = notices(out, "alert")[0]
        self.assertEqual(alert.detail["zone"], "Z1")
        self.assertFalse(alert.detail["needs_check"])
        self.assertEqual(alert.detail["confidence"], 0.9)
        self.assertEqual(s.phase, "dispatch")
        self.assertEqual((s.finder, s.guide), ("A", "B"))

        out = s.arrived("B", "manager")
        self.assertEqual(commands(out), [("B", "stop", None), ("B", "action", "nodding_motion")])
        self.assertEqual(s.phase, "at_manager")

        out = s.start_guide()
        self.assertEqual(commands(out), [("B", "guide", "site")])
        self.assertEqual(s.phase, "guiding")

        out = s.arrived("B", "site")
        self.assertEqual(commands(out), [("B", "stop", None), ("B", "pose", "sit")])
        self.assertEqual(s.phase, "on_site")

        out = s.resolved()
        self.assertEqual(commands(out), [("A", "pose", "default"), ("A", "goto", "home"),
                                         ("B", "pose", "default"), ("B", "goto", "home")])
        self.assertEqual(s.phase, "returning")
        self.assertIsNone(s.incident)

        self.assertEqual(commands(s.arrived("A", "home")), [("A", "stop", None)])
        self.assertEqual(s.phase, "returning")
        out = s.arrived("B", "home")
        self.assertEqual(commands(out), [("B", "stop", None), ("A", "patrol", None), ("B", "patrol", None)])
        self.assertEqual(s.phase, "patrol")

    def test_robot_b_can_be_finder(self):
        self.s.detection(fall("B"))
        self.assertEqual((self.s.finder, self.s.guide), ("B", "A"))
        self.assertEqual(self.s.phase, "dispatch")


class ConfidenceTests(ScenarioTestBase):
    def test_low_confidence_alerts_as_needs_check_without_dispatch(self):
        out = self.s.detection(fall("A", status="needs_check", confidence=0.5))
        self.assertTrue(notices(out, "alert")[0].detail["needs_check"])
        self.assertEqual(commands(out), [("A", "stop", None), ("A", "action", "nodding_motion")])
        self.assertEqual(self.s.phase, "alert")
        self.assertEqual(self.s.activity["B"], "patrol")

    def test_operator_ack_dispatches_needs_check_alert(self):
        self.s.detection(fall("A", status="needs_check"))
        out = self.s.operator_ack()
        self.assertEqual(commands(out), [("B", "goto", "manager")])
        self.assertTrue(self.s.incident["acked"])
        self.assertEqual(self.s.phase, "dispatch")

    def test_sustained_evidence_upgrades_alert_and_dispatches(self):
        self.s.detection(fall("A", status="needs_check", confidence=0.85))
        out = self.s.detection(fall("A", confidence=0.83))
        self.assertFalse(notices(out, "alert_update")[0].detail["needs_check"])
        self.assertEqual(commands(out), [("B", "goto", "manager")])

    def test_unconfirmed_never_alerts(self):
        out = self.s.detection(fall("A", status="unconfirmed", confidence=0.2))
        self.assertEqual(out, [])
        self.assertEqual(self.s.phase, "patrol")

    def test_unknown_vision_stops_patrol_and_is_not_treated_as_safe(self):
        out = self.s.detection({"robot": "A", "status": "unknown", "reason": "source_unavailable"})
        self.assertEqual(commands(out), [("A", "stop", None)])
        self.assertEqual(notices(out, "vision_unknown")[0].robot, "A")
        self.assertIn("A", self.s.vision_paused)
        out = self.s.detection(fall("A", status="unconfirmed"))
        self.assertEqual(commands(out), [])  # 복구돼도 스스로 다시 걷지 않음
        self.assertEqual(notices(out, "vision_restored")[0].robot, "A")
        self.assertEqual(commands(self.s.start_patrol()), [("A", "patrol", None)])

    def test_reminder_while_needs_check_unacked(self):
        self.s.detection(fall("A", status="needs_check"))
        self.clock.now = 4.9
        self.assertEqual(self.s.tick(), [])
        self.clock.now = 5
        self.assertEqual(notices(self.s.tick(), "reminder")[0].detail["phase"], "alert")
        self.clock.now = 9
        self.assertEqual(self.s.tick(), [])
        self.clock.now = 10
        self.assertEqual(len(notices(self.s.tick(), "reminder")), 1)

    def test_second_detection_during_incident_is_reported_not_hidden(self):
        self.s.detection(fall("A"))
        out = self.s.detection(fall("B"))
        self.assertEqual(notices(out, "detection_ignored")[0].detail["reason"], "incident_open")
        self.assertEqual(commands(out), [])


class SafetyTests(ScenarioTestBase):
    def test_estop_from_every_phase_stops_both_and_requires_operator(self):
        for phase in ("patrol", "dispatch", "at_manager", "guiding", "on_site"):
            with self.subTest(phase=phase):
                self.setUp()
                if phase != "patrol":
                    self.to_phase(phase)
                out = self.s.estop_all()
                self.assertEqual(commands(out), [("A", "estop", None), ("B", "estop", None)])
                self.assertEqual(self.s.phase, "estop")
                self.assertEqual(self.s.ready, set())
                self.assertEqual(commands(self.s.robot_ready("A") + self.s.robot_ready("B")), [])
                self.assertEqual(commands(self.s.tick()), [])

    def test_estop_with_open_incident_requires_resolve_before_patrol(self):
        self.to_phase("guiding")
        self.s.estop_all()
        self.s.robot_ready("A")
        self.assertEqual(notices(self.s.start_patrol(), "rejected")[0].detail["event"], "start_patrol")
        out = self.s.resolved()
        self.assertEqual(commands(out), [])
        self.assertEqual(self.s.phase, "estop")
        self.assertEqual(commands(self.s.start_patrol()), [("A", "patrol", None)])

    def test_detection_during_estop_is_reported_without_motion(self):
        self.s.estop_all()
        out = self.s.detection(fall("A"))
        self.assertEqual(commands(out), [])
        self.assertEqual(notices(out, "detection_ignored")[0].detail["reason"], "estop")

    def test_robot_ready_never_moves_a_robot(self):
        s = Scenario(clock=self.clock)
        for robot in ("A", "B"):
            self.assertEqual(commands(s.robot_ready(robot)), [])
        self.assertEqual(s.phase, "standby")

    def test_guide_link_lost_while_moving_suspends_and_retry_resumes(self):
        for phase, resume in (("dispatch", ("B", "goto", "manager")), ("guiding", ("B", "guide", "site"))):
            with self.subTest(phase=phase):
                self.setUp()
                self.to_phase(phase)
                out = self.s.link_lost("B")
                self.assertEqual(commands(out), [("B", "stop", None)])
                self.assertEqual(self.s.phase, "suspended")
                self.assertEqual(notices(out, "suspended")[0].detail["reason"], "link_lost")
                self.assertEqual(notices(self.s.retry(), "no_guide")[0].robot, "B")
                self.s.robot_ready("B")
                self.assertEqual(commands(self.s.retry()), [resume])
                self.assertEqual(self.s.phase, phase)

    def test_finder_link_lost_keeps_incident(self):
        self.to_phase("at_manager")
        out = self.s.link_lost("A")
        self.assertEqual(self.s.phase, "at_manager")
        self.assertEqual(notices(out, "link_lost")[0].robot, "A")

    def test_link_lost_during_patrol_stops_only_that_robot(self):
        out = self.s.link_lost("A")
        self.assertEqual(commands(out), [("A", "stop", None)])
        self.assertEqual(self.s.activity["B"], "patrol")

    def test_no_dispatch_when_guide_not_ready(self):
        self.s.link_lost("B")
        out = self.s.detection(fall("A"))
        self.assertEqual(notices(out, "no_guide")[0].robot, "B")
        self.assertEqual(self.s.phase, "alert")
        self.s.robot_ready("B")
        self.assertEqual(self.s.phase, "alert")
        self.assertEqual(commands(self.s.operator_ack()), [("B", "goto", "manager")])

    def test_guide_holds_when_blocked_and_resumes_on_clear(self):
        self.to_phase("guiding")
        out = self.s.guide_blocked("manager_separated")
        self.assertEqual(commands(out), [("B", "stop", None)])
        self.assertEqual(notices(self.s.arrived("B", "site"), "rejected")[0].detail["event"], "arrived")
        self.clock.now = 5
        self.assertEqual(notices(self.s.tick(), "reminder")[0].detail["hold"], "manager_separated")
        self.assertEqual(commands(self.s.guide_clear()), [("B", "guide", "site")])
        self.assertIsNone(self.s.hold)

    def test_no_command_can_reset_latch_or_use_unlisted_actions(self):
        for args in (("A", "reset"), ("A", "action", "stand_two_legs"), ("A", "action", "boxing"),
                     ("A", "pose", "prone2"), ("*", "estop"), ("A", "stop", "x"), ("A", "goto", "site")):
            with self.subTest(args=args):
                with self.assertRaises(ValueError):
                    Command(*args)


class TimeoutTests(ScenarioTestBase):
    def test_dispatch_timeout_stops_guide_and_suspends(self):
        self.to_phase("dispatch")
        self.clock.now = 9.9
        self.assertEqual(commands(self.s.tick()), [])
        self.clock.now = 10
        out = self.s.tick()
        self.assertEqual(commands(out), [("B", "stop", None)])
        self.assertEqual(notices(out, "timeout")[0].detail["phase"], "dispatch")
        self.assertEqual(self.s.resume_phase, "dispatch")

    def test_guide_timeout_counts_hold_time(self):
        self.to_phase("guiding")
        self.s.guide_blocked("obstacle")
        self.clock.now = 20
        self.s.tick()
        self.assertEqual(self.s.phase, "suspended")
        self.assertEqual(self.s.resume_phase, "guiding")
        self.assertIsNone(self.s.hold)

    def test_retry_gives_fresh_deadline(self):
        self.to_phase("dispatch")
        self.clock.now = 10
        self.s.tick()
        self.clock.now = 12
        self.s.retry()
        self.clock.now = 21.9
        self.assertEqual(self.s.phase, "dispatch")
        self.assertEqual(notices(self.s.tick(), "timeout"), [])

    def test_manager_no_response_reminds_without_moving(self):
        self.to_phase("at_manager")
        self.clock.now = 100
        out = self.s.tick()
        self.assertEqual(commands(out), [])
        self.assertEqual(notices(out, "reminder")[0].detail["phase"], "at_manager")

    def test_suspended_resolve_returns_robots(self):
        self.to_phase("dispatch")
        self.clock.now = 10
        self.s.tick()
        self.s.resolved()
        self.assertEqual(self.s.phase, "returning")

    def test_return_timeout_stops_and_waits_for_operator(self):
        self.to_phase("on_site")
        self.s.resolved()
        self.s.arrived("A", "home")
        self.clock.now = 15
        out = self.s.tick()
        self.assertEqual(commands(out), [("B", "stop", None)])
        self.assertEqual(self.s.phase, "standby")

    def test_link_lost_while_returning_patrols_only_returned_robot(self):
        self.to_phase("on_site")
        self.s.resolved()
        self.s.arrived("A", "home")
        out = self.s.link_lost("B")
        self.assertEqual(commands(out), [("B", "stop", None), ("A", "patrol", None)])
        self.assertEqual(self.s.phase, "patrol")
        self.assertEqual(commands(self.s.robot_ready("B")), [])


class EventValidationTests(ScenarioTestBase):
    def test_out_of_phase_operator_actions_are_rejected_without_commands(self):
        for event in ("start_guide", "retry", "resolved", "operator_ack", "guide_clear"):
            with self.subTest(event=event):
                out = getattr(self.s, event)()
                self.assertEqual(commands(out), [])
                self.assertEqual(notices(out, "rejected")[0].detail["event"], event)
        self.assertEqual(commands(self.s.guide_blocked("x")), [])

    def test_unexpected_arrivals_are_rejected(self):
        self.to_phase("dispatch")
        for robot, target in (("A", "manager"), ("B", "site"), ("B", "nowhere")):
            with self.subTest(robot=robot, target=target):
                self.assertEqual(notices(self.s.arrived(robot, target), "rejected")[0].robot, robot)
        self.assertEqual(self.s.phase, "dispatch")

    def test_malformed_inputs_raise(self):
        with self.assertRaises(ValueError):
            self.s.detection({"robot": "C", "status": "suspected_fall"})
        with self.assertRaises(ValueError):
            self.s.detection({"robot": "A", "status": "maybe"})
        with self.assertRaises(ValueError):
            self.s.link_lost("*")

    def test_snapshot_is_a_copy(self):
        self.s.detection(fall("A"))
        snap = self.s.snapshot()
        snap["incident"]["acked"] = True
        self.assertFalse(self.s.incident["acked"])
        self.assertEqual(snap["phase"], "dispatch")


if __name__ == "__main__":
    unittest.main()
