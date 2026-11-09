"""지도 편집의 보수적 검증. 인증·지도 확정·로봇 이동은 수행하지 않습니다."""
from dataclasses import dataclass
import hashlib
import json
import math
import re

MAX_CELLS = 1_000_000


def _finite(value):
    return (not isinstance(value, bool) and isinstance(value, (int, float))
            and math.isfinite(value))


@dataclass(frozen=True)
class Grid:
    width: int
    height: int
    resolution: float
    origin: tuple  # x, y, yaw; ROS Pose 변환은 별도 어댑터의 책임
    cells: tuple
    frame: str = "map"

    def __post_init__(self):
        for value in (self.width, self.height):
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError("invalid grid dimensions")
        size = self.width * self.height
        if size > MAX_CELLS:
            raise ValueError("grid too large")
        if not _finite(self.resolution) or self.resolution <= 0:
            raise ValueError("invalid grid resolution")
        if (not isinstance(self.origin, (tuple, list)) or len(self.origin) != 3
                or not all(_finite(v) for v in self.origin)):
            raise ValueError("invalid grid origin")
        if (not isinstance(self.cells, (tuple, list)) or len(self.cells) != size
                or any(isinstance(v, bool) or not isinstance(v, int) or not -1 <= v <= 100
                       for v in self.cells)):
            raise ValueError("invalid grid cells")
        if not isinstance(self.frame, str) or not re.fullmatch(r"[A-Za-z0-9_/]{1,64}", self.frame):
            raise ValueError("invalid grid frame")
        object.__setattr__(self, "resolution", float(self.resolution))
        object.__setattr__(self, "origin", tuple(float(v) for v in self.origin))
        object.__setattr__(self, "cells", tuple(self.cells))

    def digest(self):
        payload = json.dumps([self.width, self.height, self.resolution, self.origin,
                              self.frame, self.cells], separators=(",", ":"), allow_nan=False)
        return hashlib.sha256(payload.encode("ascii")).hexdigest()


@dataclass(frozen=True)
class EditReview:
    base_digest: str
    proposal_digest: str
    cleared_cells: tuple  # row-major index; (x, y) = (index % width, index // width)
    changed_cells: int


def review_edit(base, proposal):
    """0만 빈 칸, -1은 미확인, 1..100은 모두 막힌 칸으로 취급합니다."""
    if not isinstance(base, Grid) or not isinstance(proposal, Grid):
        raise ValueError("Grid required")
    if ((base.width, base.height, base.resolution, base.origin, base.frame)
            != (proposal.width, proposal.height, proposal.resolution, proposal.origin, proposal.frame)):
        raise ValueError("grid geometry changed")
    cleared, changed = [], 0
    for index, (before, after) in enumerate(zip(base.cells, proposal.cells)):
        changed += before != after
        if before == -1 and after == 0:
            raise ValueError("unknown cannot become free")
        if before > 0 and after == 0:
            cleared.append(index)
    return EditReview(base.digest(), proposal.digest(), tuple(cleared), changed)


def approve_edit(base, proposal, *, expected_base_digest, expected_proposal_digest,
                 approved_clearings=()):
    """인증된 상위 계층이 넘긴 두 해시와 삭제 승인 목록을 다시 대조합니다.

    성공도 주행 허가가 아닙니다. 지도 버전 확정·감사 기록은 상위 계층이 별도로 수행해야 합니다.
    """
    review = review_edit(base, proposal)
    if (expected_base_digest != review.base_digest
            or expected_proposal_digest != review.proposal_digest):
        raise ValueError("map changed since review")
    if not isinstance(approved_clearings, (tuple, list, set, frozenset)):
        raise ValueError("invalid clearing approvals")
    if any(isinstance(v, bool) or not isinstance(v, int) for v in approved_clearings):
        raise ValueError("invalid clearing approvals")
    if set(approved_clearings) != set(review.cleared_cells):
        raise ValueError("exact clearing approvals required")
    return review
