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
