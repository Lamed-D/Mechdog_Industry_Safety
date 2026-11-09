import unittest
from types import SimpleNamespace

from host.vision.camera_client import Frame
from tools.vision_performance import measure


class PerformanceTests(unittest.TestCase):
    def test_two_robot_rates_and_slow_processing_use_latest_frames(self):
        now = [0.0]
        receivers = {}
        for robot in ("A", "B"):
            rx = SimpleNamespace(frames=0, bytes_received=0, state=lambda: {"status": "streaming"})

            def latest(robot=robot, rx=rx):
                rx.frames += 1
                rx.bytes_received += 100
                return Frame(robot, b"synthetic", rx.frames, 0, now[0])

            rx.latest = latest
            receivers[robot] = rx

        def processor(data):
            now[0] += .1

        def sleep(seconds):
            now[0] += seconds

        result = measure(receivers, .5, processor=processor, clock=lambda: now[0], sleep=sleep)
        self.assertTrue(result["processor_configured"])
        self.assertFalse(result["model_accuracy_verified"])
        for value in result["robots"].values():
            self.assertEqual(value["processing_ms_p95"], 100)
            self.assertEqual(value["result_age_ms_p95"], 100)
            self.assertGreater(value["received_fps"], 0)
            self.assertEqual(value["processing_errors"], 0)

    def test_invalid_duration_does_not_read_sources(self):
        for value in (0, -1, float("nan")):
            with self.assertRaises(ValueError):
                measure({}, value)
