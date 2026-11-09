import unittest
from host.vision import EvidenceMonitor, Observation
from host.vision.evidence import from_official_result


class EvidenceTests(unittest.TestCase):
    def test_invalid_clock_values_break_window_without_raising(self):
        for value in (None, "1", True, float("nan"), float("inf"), 10 ** 1000):
            for field in ("timestamp", "now"):
                with self.subTest(value_type=type(value).__name__, field=field):
                    monitor = EvidenceMonitor(hold_s=1)
                    monitor.update(Observation("A", 0, .9, True, "synthetic"), 0)
                    timestamp, now = (value, .2) if field == "timestamp" else (.2, value)
                    result = monitor.update(Observation("A", timestamp, .9, True, "synthetic"), now)
                    self.assertEqual(result["status"], "unknown")
                    self.assertNotIn("A", monitor.windows)

    def test_invalid_configuration_is_rejected_before_use(self):
        for field in ("threshold", "hold_s", "max_gap_s"):
            for value in (None, "1", True, float("nan"), float("inf"), 10 ** 1000):
                with self.subTest(field=field, value_type=type(value).__name__), self.assertRaises(ValueError):
                    EvidenceMonitor(**{field: value})

    def test_sustained_evidence_keeps_minimum_confidence_and_source(self):
        monitor = EvidenceMonitor(hold_s=1)
        for i in range(5):
            event = monitor.update(Observation("A", i * .25, .9 - i * .01, True, "synthetic"), i * .25)
        self.assertEqual(event["status"], "suspected_fall")
        self.assertEqual(event["confidence"], .86)
        self.assertEqual(event["source"], "synthetic")

    def test_missing_low_invalid_stale_and_future_break_window(self):
        monitor = EvidenceMonitor()
        for value in (float("nan"), None, 1.1):
            event = monitor.update(Observation("A", 1, value, True, "model"), 1)
            self.assertEqual(event["status"], "unknown")
        for timestamp, now in ((1, 3), (3, 1)):
            self.assertEqual(monitor.update(Observation("A", timestamp, .9, True, "model"), now)["status"], "unknown")
        self.assertEqual(monitor.missing("A")["status"], "unknown")

    def test_face_is_never_posture_or_fall_evidence(self):
        monitor = EvidenceMonitor()
        for face in (False, True, [1, 2]):
            event = monitor.update(from_official_result("A", face, 1), 1)
            self.assertEqual(event["status"], "unknown")

    def test_duplicate_and_source_change_do_not_accumulate(self):
        monitor = EvidenceMonitor(hold_s=.5)
        monitor.update(Observation("A", 0, .9, True, "synthetic"), 0)
        self.assertEqual(monitor.update(Observation("A", 0, .9, True, "synthetic"), 0)["status"], "unknown")
        monitor.update(Observation("A", .25, .9, True, "synthetic"), .25)
        event = monitor.update(Observation("A", .5, .9, True, "model"), .5)
        self.assertEqual(event["duration_s"], 0)
