import unittest
from types import SimpleNamespace

from host.vision.camera_client import Frame
from host.vision.evidence import EvidenceMonitor
from host.vision.pipeline import VisionPump, jpeg_size


def metadata_jpeg(width=640, height=480):
    # SOF 차원 파서용 합성 바이트. 실제 그림으로 디코딩하지 않습니다.
    return b"\xff\xd8\xff\xc0\x00\x08\x08" + height.to_bytes(2, "big") + width.to_bytes(2, "big") + b"\x01\xff\xd9"


class Receiver:
    def __init__(self):
        self.frame = None

    def latest(self):
        return self.frame

    def state(self):
        return {"status": "streaming" if self.frame else "unknown"}


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.now = 10.0
        self.receivers = {r: Receiver() for r in ("A", "B")}
        self.events, self.camera = [], []
        self.core = SimpleNamespace(detection=self.events.append, camera_state=lambda *args: self.camera.append(args))

    def make(self, infer=lambda jpeg: {"candidate": True, "confidence": .9}):
        return VisionPump(self.receivers, infer, source="synthetic", clock=lambda: self.now,
                          monitor=EvidenceMonitor(hold_s=.5))

    def feed(self, robot="A", seq=1, size=(640, 480)):
        self.receivers[robot].frame = Frame(robot, metadata_jpeg(*size), seq, 0, self.now)

    def test_latest_only_and_two_robot_evidence_stays_separate(self):
        pump = self.make()
        for i in range(4):
            self.now += .2
            self.feed(seq=i)
            pump.step()
        self.assertEqual(pump.snapshot()["A"]["event"]["status"], "suspected_fall")
        self.assertEqual(pump.snapshot()["B"]["event"]["status"], "unknown")
        pump.step()  # 같은 프레임을 다시 추론하지 않음
        self.assertEqual(pump.snapshot()["A"]["processed"], 4)

    def test_slow_model_and_stale_result_are_unknown(self):
        def slow(jpeg):
            self.now += .7
            return {"candidate": True, "confidence": .99}
        self.feed()
        pump = self.make(slow)
        pump.step()
        self.assertEqual(pump.snapshot()["A"]["event"]["reason"], "inference_too_old")
        pump.apply(self.core)
        self.assertEqual(self.events[0]["status"], "unknown")

    def test_apply_never_runs_model_and_discards_delayed_results(self):
        calls = []
        pump = self.make(lambda jpeg: calls.append(jpeg) or {"candidate": True, "confidence": .9})
        self.feed()
        pump.step()
        self.now += .6
        pump.apply(self.core)
        self.assertEqual(len(calls), 1)
        self.assertEqual(self.events[0]["reason"], "inference_stale")
        pump.apply(self.core)
        self.assertEqual(len(self.events), 2)  # A·B 각각 unknown 한 번씩

    def test_missing_model_low_resolution_and_exception(self):
        self.feed()
        pump = self.make(None)
        pump.step()
        self.assertEqual(pump.snapshot()["A"]["event"]["reason"], "model_unavailable")
        pump = self.make()
        self.feed(size=(320, 240))
        pump.step()
        self.assertEqual(pump.snapshot()["A"]["event"]["reason"], "insufficient_resolution")
        self.feed(seq=2)
        pump = self.make(lambda jpeg: {} )
        pump.step()
        self.assertEqual(pump.snapshot()["A"]["event"]["reason"], "inference_failed")

    def test_metadata_dimensions_and_truncation(self):
        self.assertEqual(jpeg_size(metadata_jpeg(800, 600)), (800, 600))
        for data in (b"not jpeg", metadata_jpeg()[:9], metadata_jpeg(0, 480)):
            self.assertIsNone(jpeg_size(data))

    def test_stale_or_future_frame_never_calls_model(self):
        for captured in (self.now - .6, self.now + .1):
            calls = []
            self.receivers["A"].frame = Frame("A", metadata_jpeg(), 1, 0, captured)
            pump = self.make(lambda jpeg: calls.append(jpeg) or {"candidate": True, "confidence": .9})
            pump.step()
            self.assertEqual(calls, [])
            self.assertEqual(pump.snapshot()["A"]["event"]["status"], "unknown")

    def test_invalid_or_wrong_robot_frame_does_not_kill_other_receiver(self):
        for frame in (object(), Frame("B", metadata_jpeg(), 1, 0, self.now),
                      Frame("A", metadata_jpeg(), True, 0, self.now),
                      Frame("A", metadata_jpeg(), 1, 0, 10 ** 1000),
                      Frame("A", metadata_jpeg(), 1, 0, float("nan"))):
            with self.subTest(frame=frame):
                self.receivers["A"].frame = frame
                self.feed("B")
                pump = self.make()
                pump.step()
                self.assertEqual(pump.snapshot()["A"]["event"]["status"], "unknown")
                self.assertEqual(pump.snapshot()["B"]["event"]["status"], "needs_check")

    def test_malformed_receiver_state_is_unknown_in_control_loop(self):
        self.receivers["A"].state = lambda: None
        pump = self.make()
        pump.apply(self.core)
        self.assertEqual(self.events[0]["status"], "unknown")

    def test_invalid_result_age_configuration_is_rejected(self):
        for age in (True, None, "0.5", float("inf"), 10 ** 1000):
            with self.subTest(age_type=type(age).__name__), self.assertRaises(ValueError):
                VisionPump(self.receivers, None, source="synthetic", max_result_age_s=age)

    def test_frame_context_refers_to_processed_frame_and_is_not_mutable(self):
        self.feed(seq=1)

        def infer(jpeg):
            self.feed(seq=99, size=(800, 600))
            return {"candidate": True, "confidence": .9}

        pump = self.make(infer)
        pump.step()
        context = pump.snapshot()["A"]["event"]["frame"]
        self.assertEqual((context["seq"], context["width"], context["height"]), (1, 640, 480))
        self.assertEqual(len(context["sha256"]), 64)
        context["seq"] = 0
        self.assertEqual(pump.snapshot()["A"]["event"]["frame"]["seq"], 1)
