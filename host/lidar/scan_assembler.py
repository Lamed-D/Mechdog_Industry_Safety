"""Bounded revolution assembly; partial first/last revolutions are omitted."""

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class Scan:
    angles_deg: tuple
    distances_mm: tuple
    qualities: tuple


class ScanAssembler:
    def __init__(self, mounting_angle_deg=0, direction=1, max_samples=8192):
        if direction not in (-1, 1) or not math.isfinite(mounting_angle_deg):
            raise ValueError("invalid angle correction")
        if max_samples < 2:
            raise ValueError("max_samples must be at least two")
        self.offset = mounting_angle_deg
        self.direction = direction
        self.max_samples = max_samples
        self.reset()

    def reset(self):
        self.samples = None

    def add(self, sample):
        scan = None
        if sample.start:
            if self.samples:
                scan = Scan(
                    tuple((self.offset + self.direction * s.angle_deg) % 360
                          for s in self.samples),
                    tuple(s.distance_mm for s in self.samples),
                    tuple(s.quality for s in self.samples))
            self.samples = []
        if self.samples is not None:
            self.samples.append(sample)
            if len(self.samples) > self.max_samples:
                self.reset()
        return scan
