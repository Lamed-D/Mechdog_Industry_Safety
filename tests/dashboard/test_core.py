import json
import math
import unittest
from types import SimpleNamespace

from dashboard.core import DashboardCore, EventLog
from scenario.machine import Command, Scenario


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


class FakeLink:
    """RobotLink 과 같은 모양의 가짜 링크."""

    def __init__(self, clock, fail_estop=False):
        self.clock = clock
        self.fail_estop = fail_estop
        self.latest = None
        self.last_seen = -math.inf
        self.estops = 0
        self.steps = 0
        self.resets = 0

    def telemetry(self, latched=False, reason="none", battery=7800):
        self.latest = SimpleNamespace(latched=latched, reason=reason, battery_mv=battery, warnings=frozenset())
        self.last_seen = self.clock()

    def fresh(self):
        return self.latest is not None and 0 <= self.clock() - self.last_seen < 0.4

    def status(self):
        if self.latest is None or self.clock() - self.last_seen >= 1:
            return "unknown"
        return "stopped" if self.latest.latched else "idle"

    def estop(self):
        if self.fail_estop:
            raise OSError("send failed")
        self.estops += 1

    def step(self):
        self.steps += 1

    def request_reset(self):
        if not self.fresh() or not self.latest.latched:
            raise ValueError("reset requires fresh latched telemetry and adequate battery")
        self.resets += 1


def fall(robot="A", status="suspected_fall"):
    return {"robot": robot, "status": status, "confidence": 0.9, "source": "synthetic",
            "duration_s": 2.0, "threshold": 0.8, "hold_s": 2.0}


class DashboardCoreTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.links = {"A": FakeLink(self.clock), "B": FakeLink(self.clock)}
        self.log = EventLog(wall=lambda: 1.7e9)
        self.addCleanup(self.log.close)
        self.core = DashboardCore(Scenario(clock=self.clock), self.links, self.log,
                                  clock=self.clock, wall=lambda: 1.7e9)

    def ready_both(self):
        for link in self.links.values():
            link.telemetry()
        self.core.update()

    def test_estop_all_reaches_every_link_and_pushes_immediately(self):
        self.ready_both()
        result = self.core.estop_all()
        self.assertTrue(result["ok"])
        self.assertEqual(result["sent"], ["A", "B"])
        for link in self.links.values():
            self.assertGreaterEqual(link.estops, 1)
            self.assertEqual(link.steps, 1)
        self.assertEqual(self.core.snapshot()["phase"], "estop")
        self.assertEqual(self.log.recent(50)[0]["kind"], "estop_all")

    def test_estop_continues_when_one_link_scenario_or_log_fails(self):
        self.links["A"].fail_estop = True
        self.log.close()                                   # 기록 실패
        self.core.scenario.estop_all = lambda: 1 / 0       # 시나리오 실패
        result = self.core.estop_all()
        self.assertFalse(result["ok"])
        self.assertEqual(result["sent"], ["B"])
        self.assertEqual(self.links["B"].estops, 1)
        self.assertEqual({e["error"] for e in result["errors"]}, {"OSError", "scenario_ZeroDivisionError"})
        self.assertGreater(self.core.snapshot()["log_failures"], 0)

    def test_missing_link_is_reported_not_ignored(self):
        core = DashboardCore(Scenario(clock=self.clock), {"A": self.links["A"]}, self.log, clock=self.clock)
        result = core.estop_all()
        self.assertEqual(result["errors"], [{"robot": "B", "error": "no_link"}])

    def test_reset_requires_confirmation_and_latched_fresh_robot(self):
        self.assertEqual(self.core.reset_latch("A")["reason"], "confirmation_required")
        self.assertEqual(self.links["A"].resets, 0)
        self.assertFalse(self.core.reset_latch("A", confirmed=True)["ok"])   # 텔레메트리 없음
        self.links["A"].telemetry(latched=True, reason="estop")
        self.assertTrue(self.core.reset_latch("A", confirmed=True)["ok"])
        self.assertEqual(self.links["A"].resets, 1)
        with self.assertRaises(ValueError):
            self.core.reset_latch("C", confirmed=True)

    def test_ready_only_after_fresh_unlatched_telemetry(self):
        self.links["A"].telemetry(latched=True, reason="boot")
        self.core.update()
        self.assertEqual(self.core.scenario.snapshot()["ready"], [])
        self.links["A"].telemetry()
        self.core.update()
        self.assertEqual(self.core.scenario.snapshot()["ready"], ["A"])

    def test_link_loss_and_robot_latch_remove_readiness_and_stop(self):
        self.ready_both()
        self.assertTrue(self.core.operator("start_patrol")["ok"])
        self.core.drain_commands()
        self.clock.now += 0.5                              # A 끊김, B 는 새 텔레메트리
        self.links["B"].telemetry(latched=True, reason="low_battery")
        self.core.update()
        self.assertEqual(self.core.scenario.snapshot()["ready"], [])
        stops = {(c.robot, c.kind) for c in self.core.drain_commands()}
        self.assertEqual(stops, {("A", "stop"), ("B", "stop")})
        kinds = [n["kind"] for n in self.core.snapshot()["notices"]]
        self.assertIn("link_lost", kinds)
        self.assertIn("robot_latched", kinds)
        self.assertEqual(self.core.snapshot()["robots"]["A"]["link"], "stale")

    def test_alert_lifecycle_and_commands_for_adapter(self):
        self.ready_both()
        self.core.detection(fall("A"), zone="Z1")
        alerts = self.core.snapshot()["alerts"]
        self.assertEqual(len(alerts), 1)
        self.assertEqual((alerts[0]["robot"], alerts[0]["zone"], alerts[0]["state"]), ("A", "Z1", "open"))
        commands = self.core.drain_commands()
        self.assertIn(Command("A", "stop"), commands)
        self.assertIn(Command("B", "goto", "manager"), commands)
        self.core.operator("operator_ack")
        self.assertTrue(self.core.snapshot()["alerts"][0]["acked"])
        self.core.operator("resolved")
        self.assertEqual(self.core.snapshot()["alerts"][0]["state"], "resolved")

    def test_needs_check_alert_waits_for_person(self):
        self.ready_both()
        self.core.detection(fall("A", "needs_check"))
        self.assertNotIn(Command("B", "goto", "manager"), self.core.drain_commands())
        self.assertTrue(self.core.snapshot()["alerts"][0]["needs_check"])
        self.core.operator("operator_ack")
        self.assertIn(Command("B", "goto", "manager"), self.core.drain_commands())

    def test_rejected_operator_event_and_unknown_event(self):
        result = self.core.operator("start_guide")
        self.assertFalse(result["ok"])
        with self.assertRaises(ValueError):
            self.core.operator("estop_all")    # 전체 정지는 전용 메서드로만

    def test_camera_state_and_snapshot_is_json(self):
        self.core.camera_state("A", {"robot": "A", "status": "streaming"})
        self.core.camera_state("B", None)
        snap = self.core.snapshot()
        self.assertEqual((snap["robots"]["A"]["camera"], snap["robots"]["B"]["camera"]), ("streaming", "unknown"))
        json.dumps(snap)

    def test_log_never_stores_raw_bytes(self):
        self.log.record("photo", "A", {"jpeg": b"\xff\xd8...", "path": "/srv/local/1.jpg"})
        detail = self.log.recent(1)[0]["detail"]
        self.assertEqual(detail["jpeg"], "<bytes omitted>")
        self.assertEqual(detail["path"], "/srv/local/1.jpg")


if __name__ == "__main__":
    unittest.main()
