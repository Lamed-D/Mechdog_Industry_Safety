import unittest
from unittest.mock import patch

from tools.mock.demo_scenario import run_demo


class SyntheticDemoTests(unittest.TestCase):
    def test_both_robot_ids_complete_without_opening_any_socket(self):
        with patch("socket.socket", side_effect=AssertionError("hardware/network forbidden")):
            for finder in ("A", "B"):
                result = run_demo(finder)
                self.assertTrue(result["complete"])
                self.assertEqual(result["phase"], "patrol")
                phases = {row["phase"] for row in result["timeline"]}
                self.assertTrue({"patrol", "alert", "dispatch", "at_manager", "guiding", "on_site", "returning"} <= phases)
                self.assertTrue(all(row["source"] == "synthetic" and not row["hardware"] for row in result["timeline"]))
                guide = "B" if finder == "A" else "A"
                alert = next(row["detail"] for row in result["timeline"] if row["event"] == "fall_alert")
                self.assertEqual(alert, {"finder": finder, "guide": guide, "alerts": 1})
                commands = [row["detail"] for row in result["timeline"] if row["event"] == "command"]
                self.assertIn({"robot": guide, "kind": "goto", "arg": "manager"}, commands)
                self.assertIn({"robot": guide, "kind": "guide", "arg": "site"}, commands)

    def test_fault_recovery_is_scripted_operator_and_estop_does_not_resume(self):
        for fault in ("link", "camera"):
            result = run_demo(fault=fault)
            self.assertTrue(result["complete"])
            paused = [r for r in result["timeline"] if r["event"] in ("link_lost", "camera_lost", "camera_restored")]
            self.assertTrue(all(r["phase"] == "suspended" for r in paused))
            self.assertTrue(any(r["event"] == "scripted_operator" and r["detail"]["event"] == "retry"
                                for r in result["timeline"]))
        result = run_demo(fault="estop")
        self.assertFalse(result["complete"])
        self.assertTrue(result["safely_stopped"])
        self.assertEqual(result["phase"], "estop")

    def test_link_loss_stops_the_assigned_guide_before_operator_retry(self):
        rows = run_demo(finder="B", fault="link")["timeline"]
        loss = next(i for i, row in enumerate(rows) if row["event"] == "link_lost")
        self.assertEqual(rows[loss]["detail"], {"robot": "A", "latched": True})
        self.assertTrue(any(row["event"] == "command" and row["detail"]["robot"] == "A"
                            and row["detail"]["kind"] == "stop" and row["phase"] == "suspended"
                            for row in rows[:loss]))
        retry = next(i for i, row in enumerate(rows)
                     if row["event"] == "scripted_operator" and row["detail"]["event"] == "retry")
        self.assertFalse(any(row["event"] == "command" and row["detail"]["kind"] in ("goto", "guide")
                             for row in rows[loss:retry]))
