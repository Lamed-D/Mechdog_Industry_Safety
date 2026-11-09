"""최신 JPEG 한 장만 추론하는 작업자. 모델은 주입하며 영상·얼굴을 저장하지 않습니다."""
from collections import deque
from copy import deepcopy
import hashlib
import math
import threading
import time

from host.vision.evidence import EvidenceMonitor, Observation
from host.vision.camera_client import Frame, MAX_FRAME_BYTES, is_jpeg


def jpeg_size(data):
    """SOF의 크기만 확인합니다. 실제 JPEG 디코딩 성공을 대신하지 않습니다."""
    if data[:2] != b"\xff\xd8":
        return None
    pos = 2
    while pos + 3 < len(data):
        if data[pos] != 255:
            return None
        while pos < len(data) and data[pos] == 255:
            pos += 1
        if pos >= len(data):
            return None
        marker = data[pos]
        pos += 1
        if marker in (0xDA, 0xD9):
            return None
        length = int.from_bytes(data[pos:pos + 2], "big")
        if length < 2 or pos + length > len(data):
            return None
        if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
            if length < 8:
                return None
            height, width = int.from_bytes(data[pos + 3:pos + 5], "big"), int.from_bytes(data[pos + 5:pos + 7], "big")
            return (width, height) if width and height else None
        pos += length
    return None


class VisionPump:
    def __init__(self, receivers, infer, *, source, clock=time.monotonic, max_result_age_s=0.5, monitor=None):
        if set(receivers) != {"A", "B"} or source not in ("model", "synthetic"):
            raise ValueError("both robots and explicit evidence source required")
        if not math.isfinite(max_result_age_s) or max_result_age_s <= 0:
            raise ValueError("invalid result age")
        self.receivers, self.infer, self.source, self.clock = receivers, infer, source, clock
        self.max_age = max_result_age_s
        self.monitor = monitor or EvidenceMonitor()
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None
        self._last_frame, self._results, self._applied = {}, {}, {}
        self._revision = 0
        self._metrics = {r: {"processed": 0, "errors": 0, "latencies": deque(maxlen=200)} for r in receivers}

    def step(self):
        # 네트워크 수신은 LatestFrameReceiver가 별도 스레드에서 계속합니다.
        for robot, receiver in self.receivers.items():
            try:
                frame = receiver.latest()
            except Exception:
                frame = None
            if frame is None:
                self._publish(robot, self.monitor.missing(robot), None)
                continue
            if (not isinstance(frame, Frame) or frame.robot != robot
                    or type(frame.seq) is not int or frame.seq < 0
                    or isinstance(frame.captured_at, bool) or not isinstance(frame.captured_at, (int, float))
                    or not math.isfinite(frame.captured_at) or not isinstance(frame.jpeg, bytes)
                    or not 0 < len(frame.jpeg) <= MAX_FRAME_BYTES or not is_jpeg(frame.jpeg)):
                self._metrics[robot]["errors"] += 1
                self._publish(robot, self.monitor.missing(robot), None, "invalid_frame")
                continue
            identity = (frame.seq, frame.captured_at)
            if self._last_frame.get(robot) == identity:
                continue  # 같은 프레임을 재추론해 시간 창을 채우지 않음
            self._last_frame[robot] = identity
            if not 0 <= self.clock() - frame.captured_at <= self.max_age:
                self._publish(robot, self.monitor.missing(robot), None, "stale_before_inference")
                continue
            if self.infer is None:
                self._publish(robot, self.monitor.missing(robot), None, "model_unavailable")
                continue
            dimensions = jpeg_size(frame.jpeg)
            if dimensions is None or dimensions[0] < 640 or dimensions[1] < 480:
                self._publish(robot, self.monitor.missing(robot), None, "insufficient_resolution")
                continue
            started = self.clock()
            metrics = self._metrics[robot]
            metrics["processed"] += 1
            try:
                answer = self.infer(frame.jpeg)  # 디코딩·전처리·추론. 로봇/대시보드 잠금 밖.
                now = self.clock()
                metrics["latencies"].append((now - started) * 1000)
                if not 0 <= now - frame.captured_at <= self.max_age:
                    event = self.monitor.missing(robot)
                    event["reason"] = "inference_too_old"
                else:
                    event = self.monitor.update(Observation(robot, frame.captured_at,
                        answer["confidence"], answer["candidate"], self.source), now)
            except Exception:
                metrics["errors"] += 1
                event = self.monitor.missing(robot)
                event["reason"] = "inference_failed"
            if event.get("status") in ("needs_check", "suspected_fall"):
                event["frame"] = {"seq": frame.seq, "width": dimensions[0], "height": dimensions[1],
                                  "captured_at": frame.captured_at, "sha256": hashlib.sha256(frame.jpeg).hexdigest()}
            self._publish(robot, event, frame.captured_at)

    def _publish(self, robot, event, captured, reason=None):
        if reason:
            event = {**event, "reason": reason}
        metrics = self._metrics[robot]
        values = sorted(metrics["latencies"])
        p95 = values[max(0, math.ceil(len(values) * .95) - 1)] if values else None
        with self._lock:
            self._revision += 1
            self._results[robot] = {"event": dict(event), "captured": captured,
                "revision": self._revision, "processed": metrics["processed"],
                "errors": metrics["errors"], "inference_ms_p95": p95}

    def snapshot(self):
        with self._lock:
            return deepcopy(self._results)

    def apply(self, core):
        """로봇 제어 루프에서 호출. 수신 상태·완료 결과만 읽으며 모델을 부르지 않습니다."""
        results = self.snapshot()
        for robot, receiver in self.receivers.items():
            try:
                state = receiver.state()
            except Exception:
                state = {"status": "unknown"}
            if (not isinstance(state, dict) or state.get("robot", robot) != robot
                    or state.get("status") not in ("streaming", "unknown")):
                state = {"status": "unknown", "reason": "invalid_receiver_state"}
            core.camera_state(robot, state)
            value = results.get(robot)
            if state.get("status") != "streaming":
                event, key = {"robot": robot, "status": "unknown", "reason": "camera_unavailable"}, "camera"
            elif value is None:
                event, key = {"robot": robot, "status": "unknown", "reason": "model_pending"}, "pending"
            elif value["captured"] is not None and not 0 <= self.clock() - value["captured"] <= self.max_age:
                event, key = {"robot": robot, "status": "unknown", "reason": "inference_stale"}, "stale"
            else:
                event, key = value["event"], value["revision"]
            if event.get("status") == "unknown":
                key = ("unknown", event.get("reason"))
            if self._applied.get(robot) != key:
                core.detection(event)
                self._applied[robot] = key

    def start(self):
        if self._thread is None:
            def run():
                while not self._stop.is_set():
                    self.step()
                    self._stop.wait(.02)
            self._thread = threading.Thread(target=run, name="vision-inference", daemon=True)
            self._thread.start()
        return self

    def stop(self, join_s=2):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(join_s)
