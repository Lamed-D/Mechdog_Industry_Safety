import unittest
from host.vision import EvidenceMonitor, Observation
from host.vision.evidence import from_official_result


class EvidenceTests(unittest.TestCase):
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
