"""Conservative event aggregation for an explicitly configured inference adapter."""
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class Observation:
    robot: str
    timestamp: float
    confidence: float | None
    candidate: bool | None
    source: str


class EvidenceMonitor:
    def __init__(self, threshold=0.8, hold_s=2.0, max_gap_s=0.5):
        if not (0 < threshold <= 1 and math.isfinite(hold_s) and hold_s > 0
                and math.isfinite(max_gap_s) and max_gap_s > 0):
            raise ValueError("invalid evidence thresholds")
        self.threshold, self.hold_s, self.max_gap_s = threshold, hold_s, max_gap_s
        self.windows = {}
        self.latest = {}

    def update(self, observation, now):
        item = observation
        if item.robot not in ("A", "B"):
            raise ValueError("unknown robot")
        valid = (math.isfinite(now) and math.isfinite(item.timestamp)
                 and 0 <= now - item.timestamp <= self.max_gap_s
                 and item.candidate in (True, False) and isinstance(item.candidate, bool)
                 and isinstance(item.confidence, (int, float)) and not isinstance(item.confidence, bool)
                 and math.isfinite(item.confidence) and 0 <= item.confidence <= 1
                 and item.source in ("model", "synthetic"))
        previous = self.latest.get(item.robot)
        if previous is not None and item.timestamp <= previous:
            valid = False
        if not valid:
            self.windows.pop(item.robot, None)
            return {"robot": item.robot, "status": "unknown", "reason": "invalid_or_missing_evidence"}
        self.latest[item.robot] = item.timestamp
        if not item.candidate or item.confidence < self.threshold:
            self.windows.pop(item.robot, None)
            return {"robot": item.robot, "status": "unconfirmed", "confidence": item.confidence,
                    "source": item.source}
        window = self.windows.get(item.robot)
        if window is None or item.timestamp - window[1] > self.max_gap_s or window[3] != item.source:
            window = (item.timestamp, item.timestamp, item.confidence, item.source)
        window = (window[0], item.timestamp, min(window[2], item.confidence), item.source)
        self.windows[item.robot] = window
        return {"robot": item.robot,
                "status": "suspected_fall" if item.timestamp - window[0] >= self.hold_s else "needs_check",
                "confidence": window[2], "source": item.source, "duration_s": item.timestamp - window[0],
                "threshold": self.threshold, "hold_s": self.hold_s}

    def missing(self, robot):
        self.windows.pop(robot, None)
        return {"robot": robot, "status": "unknown", "reason": "source_unavailable"}


def from_official_result(robot, result, timestamp):
    """Official face results do not contain posture evidence, regardless of face presence."""
    return Observation(robot, timestamp, None, None, "official_face")
