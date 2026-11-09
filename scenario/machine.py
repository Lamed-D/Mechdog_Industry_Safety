"""시연 시나리오 상태기계 (docs/demo-scenario.md 3·4절).

입력은 명시적인 이벤트 메서드, 출력은 고수준 Command·Notice 목록입니다.
네트워크·하드웨어·프로토콜 문자열을 다루지 않으며, 호스트 쪽 어댑터가 Command를 규약 명령으로 바꿉니다.

안전 원칙
- 이 모듈은 RESET(래치 해제)을 만들지 않습니다. 래치 해제는 대시보드의 사람 조작으로만 합니다.
- 로봇이 다시 준비되었다는 이벤트(robot_ready)만으로는 어떤 로봇도 움직이지 않습니다.
- 감지가 불확실(needs_check)하면 알림은 보내되 "확인 필요"로 표시하고, 사람 확인 전에는 호출하지 않습니다.
- 감지 결과를 모르면(unknown) 그 로봇의 순찰을 멈추고 알립니다. "위험 없음"으로 보지 않습니다.
- 링크 끊김·시간 초과·전체 정지는 해당 로봇을 멈추는 쪽으로 끝납니다.
"""
from dataclasses import dataclass, field
import time

ROBOTS = ("A", "B")
PHASES = ("standby", "patrol", "alert", "dispatch", "at_manager", "guiding",
          "on_site", "returning", "suspended", "estop")
# 명령 종류와 허용 인자. ACTION은 docs/protocol.md 3.3절 허용 목록 중 이 시나리오에 필요한 것만 씁니다.
COMMAND_ARGS = {
    "stop": None,
    "estop": None,
    "patrol": None,
    "goto": ("manager", "home"),   # 일반 걸음으로 목표 위치까지 (경로는 호스트가 계획)
    "guide": ("site",),            # 크고 느린 걸음으로 관리자를 사고 지점까지 안내
    "action": ("nodding_motion",),
    "pose": ("default", "sit"),
}
ACTIVITY = {"stop": "stopped", "estop": "estop", "patrol": "patrol", ("goto", "manager"): "to_manager",
            ("goto", "home"): "to_home", "guide": "guiding", "action": "signal",
            ("pose", "default"): "standing", ("pose", "sit"): "sitting"}
DETECTION = ("suspected_fall", "needs_check", "unconfirmed", "unknown")


@dataclass(frozen=True)
class Command:
    robot: str
    kind: str
    arg: str | None = None

    def __post_init__(self):
        if self.robot not in ROBOTS or self.kind not in COMMAND_ARGS:
            raise ValueError("unknown robot or command")
        allowed = COMMAND_ARGS[self.kind]
        if (allowed is None) != (self.arg is None) or (allowed and self.arg not in allowed):
            raise ValueError("invalid command argument")


@dataclass(frozen=True)
class Notice:
    kind: str
    robot: str | None = None
    detail: dict = field(default_factory=dict, compare=True, hash=False)


@dataclass(frozen=True)
class Timeouts:
    """모두 실측 전 [가정] 값(초)."""
    dispatch_s: float = 120.0   # 호출 후 관리자 위치 도착까지
    guide_s: float = 180.0      # 안내 시작 후 사고 지점 도착까지(멈춤 포함)
    return_s: float = 180.0     # 복귀 시작 후 시작 위치 도착까지
    remind_s: float = 30.0      # 사람 응답을 기다릴 때 다시 알리는 간격


class Scenario:
    def __init__(self, clock=time.monotonic, timeouts=Timeouts()):
        self.clock, self.t = clock, timeouts
        self.phase = "standby"
        self.ready = set()
        self.activity = {r: "idle" for r in ROBOTS}
        self.vision_paused = set()
        self.incident = None
        self.finder = self.guide = None
        self.hold = None
        self.resume_phase = None
        self.returning = set()
        self.returned = set()
        self.deadline = self.remind_at = None
        self._next_id = 1

    # ---- 상태 조회 -------------------------------------------------------
    def snapshot(self):
        return {"phase": self.phase, "ready": sorted(self.ready), "activity": dict(self.activity),
                "incident": dict(self.incident) if self.incident else None,
                "finder": self.finder, "guide": self.guide, "hold": self.hold,
                "vision_paused": sorted(self.vision_paused)}

    # ---- 로봇·감지 이벤트 -------------------------------------------------
    def detection(self, result, zone=None):
        """host.vision.EvidenceMonitor 결과(dict)를 받습니다."""
        robot, status = result.get("robot"), result.get("status")
        _robot(robot)
        if status not in DETECTION:
            raise ValueError("unknown detection status")
        out = []
        if status == "unknown":
            out.append(Notice("vision_unknown", robot, {"reason": result.get("reason")}))
            if self.activity[robot] == "patrol":
                self._cmd(out, robot, "stop")
                self.vision_paused.add(robot)
            return out
        if status == "unconfirmed":
            if robot in self.vision_paused:
                self.vision_paused.discard(robot)
                out.append(Notice("vision_restored", robot))
            return out
        needs_check = status == "needs_check"
        if self.incident:
            if robot == self.finder and not needs_check and self.incident["needs_check"]:
                self.incident.update(needs_check=False, confidence=result.get("confidence"),
                                     duration_s=result.get("duration_s"))
                out.append(Notice("alert_update", robot, dict(self.incident)))
                if self.phase == "alert":
                    self._dispatch(out)
            else:
                out.append(Notice("detection_ignored", robot, {"reason": "incident_open", "status": status}))
            return out
        if self.phase not in ("standby", "patrol", "returning"):
            out.append(Notice("detection_ignored", robot, {"reason": self.phase, "status": status}))
            return out
        self.incident = {"id": self._next_id, "robot": robot, "zone": zone or "unknown",
                         "time": self.clock(), "status": status, "needs_check": needs_check,
                         "confidence": result.get("confidence"), "source": result.get("source"),
                         "threshold": result.get("threshold"), "duration_s": result.get("duration_s"),
                         "acked": False}
        self._next_id += 1
        self.finder, self.guide = robot, _other(robot)
        self.returning.discard(robot)
        self._cmd(out, robot, "stop")
        self._cmd(out, robot, "action", "nodding_motion")
        out.append(Notice("alert", robot, dict(self.incident)))
        self._set_phase(out, "alert")
        if not needs_check:
            self._dispatch(out)
        return out

    def arrived(self, robot, target):
        _robot(robot)
        out = []
        if target == "home" and self.activity[robot] == "to_home":
            self._cmd(out, robot, "stop")
            self.activity[robot] = "idle"
            if self.phase == "returning" and robot in self.returning:
                self.returning.discard(robot)
                self.returned.add(robot)
                self._finish_return(out)
        elif target == "manager" and self.phase == "dispatch" and robot == self.guide:
            self._cmd(out, robot, "stop")
            self._cmd(out, robot, "action", "nodding_motion")
            self._set_phase(out, "at_manager")
        elif target == "site" and self.phase == "guiding" and robot == self.guide and not self.hold:
            self._cmd(out, robot, "stop")
            self._cmd(out, robot, "pose", "sit")
            self._set_phase(out, "on_site")
        else:
            out.append(_rejected("arrived", self.phase, robot=robot, target=target))
        return out

    def link_lost(self, robot):
        _robot(robot)
        self.ready.discard(robot)
        out = [Notice("link_lost", robot)]
        if self.activity[robot] not in ("idle", "stopped", "estop"):
            self._cmd(out, robot, "stop")
        if robot == self.guide and self.phase in ("dispatch", "guiding"):
            self._suspend(out, "link_lost")
        elif self.phase == "returning" and robot in self.returning:
            self.returning.discard(robot)
            self._finish_return(out)
        return out

    def robot_ready(self, robot):
        """텔레메트리가 신선하고 래치가 풀렸음. 이것만으로는 움직이지 않습니다."""
        _robot(robot)
        self.ready.add(robot)
        return [Notice("robot_ready", robot)]

    def guide_blocked(self, reason):
        """안내 중 관리자와 떨어짐·장애물 등: 안내 로봇을 멈추고 기다립니다."""
        if self.phase != "guiding" or self.hold:
            return [_rejected("guide_blocked", self.phase)]
        out = []
        self.hold = reason
        self._cmd(out, self.guide, "stop")
        self.remind_at = self.clock() + self.t.remind_s
        out.append(Notice("guide_hold", self.guide, {"reason": reason}))
        return out

    def guide_clear(self):
        if self.phase != "guiding" or not self.hold:
            return [_rejected("guide_clear", self.phase)]
        out = []
        self.hold, self.remind_at = None, None
        self._cmd(out, self.guide, "guide", "site")
        out.append(Notice("guide_resume", self.guide))
        return out

    # ---- 사람 조작 (대시보드) ----------------------------------------------
    def start_patrol(self):
        if self.phase not in ("standby", "estop", "patrol") or self.incident:
            return [_rejected("start_patrol", self.phase)]
        movers = sorted(r for r in self.ready if self.activity[r] != "patrol")
        if not movers:
            return [_rejected("start_patrol", self.phase, reason="no_ready_robot")]
        out = []
        for robot in movers:
            self.vision_paused.discard(robot)
            self._cmd(out, robot, "patrol")
        if self.phase != "patrol":
            self._set_phase(out, "patrol")
        return out

    def operator_ack(self):
        """알림 확인. 확인 필요 알림은 이 조작 뒤에 호출합니다."""
        if not self.incident:
            return [_rejected("operator_ack", self.phase)]
        self.incident["acked"] = True
        out = [Notice("alert_acked", self.finder, {"id": self.incident["id"]})]
        if self.phase == "alert":
            self._dispatch(out)
        return out

    def start_guide(self):
        """관리자가 안내 로봇 앞에서 '안내 시작'을 누름."""
        if self.phase != "at_manager":
            return [_rejected("start_guide", self.phase)]
        return self._enter_guide_phase("guiding")

    def retry(self):
        """시간 초과·링크 끊김으로 멈춘 호출/안내를 사람이 다시 시작."""
        if self.phase != "suspended":
            return [_rejected("retry", self.phase)]
        return self._enter_guide_phase(self.resume_phase)

    def resolved(self):
        """조치 완료(오탐 처리 포함). 사고를 닫고 준비된 로봇을 시작 위치로 돌려보냅니다."""
        if not self.incident:
            return [_rejected("resolved", self.phase)]
        out = [Notice("resolved", self.finder, {"id": self.incident["id"]})]
        self.incident = self.finder = self.guide = self.hold = self.resume_phase = None
        if self.phase == "estop":
            self.remind_at = None
            return out
        self.returning, self.returned = set(self.ready), set()
        for robot in sorted(self.returning):
            self._cmd(out, robot, "pose", "default")
            self._cmd(out, robot, "goto", "home")
        if self.returning:
            self._set_phase(out, "returning")
        else:
            self._set_phase(out, "standby")
        return out

    def estop_all(self):
        """전체 정지: 확인 없이 두 로봇 모두 ESTOP. 로봇은 래치되므로 준비 상태를 지웁니다."""
        out = []
        for robot in ROBOTS:
            self._cmd(out, robot, "estop")
        self.ready.clear()
        self.returning.clear()
        self.hold = None
        self._set_phase(out, "estop")
        return out

    # ---- 시간 ------------------------------------------------------------
    def tick(self):
        now, out = self.clock(), []
        if self.deadline is not None and now >= self.deadline:
            out.append(Notice("timeout", self.guide, {"phase": self.phase}))
            if self.phase == "returning":
                for robot in sorted(self.returning):
                    self._cmd(out, robot, "stop")
                self.returning.clear()
                self._set_phase(out, "standby")
            else:
                self._suspend(out, "timeout")
        if self.remind_at is not None and now >= self.remind_at:
            out.append(Notice("reminder", self.finder, {"phase": self.phase, "hold": self.hold,
                                                        "id": self.incident and self.incident["id"]}))
            self.remind_at = now + self.t.remind_s
        return out

    # ---- 내부 ------------------------------------------------------------
    def _cmd(self, out, robot, kind, arg=None):
        command = Command(robot, kind, arg)
        out.append(command)
        self.activity[robot] = ACTIVITY.get((kind, arg), ACTIVITY.get(kind))

    def _set_phase(self, out, phase):
        now = self.clock()
        self.phase = phase
        limit = {"dispatch": self.t.dispatch_s, "guiding": self.t.guide_s, "returning": self.t.return_s}.get(phase)
        self.deadline = None if limit is None else now + limit
        waiting = phase in ("alert", "at_manager", "suspended")
        self.remind_at = now + self.t.remind_s if waiting else None
        out.append(Notice("phase", None, {"phase": phase}))

    def _dispatch(self, out):
        if self.guide not in self.ready:
            out.append(Notice("no_guide", self.guide, {"id": self.incident["id"]}))
            return
        self._cmd(out, self.guide, "goto", "manager")
        self._set_phase(out, "dispatch")

    def _enter_guide_phase(self, phase):
        if self.guide not in self.ready:
            return [Notice("no_guide", self.guide, {"id": self.incident["id"]})]
        out = []
        self.hold = None
        if phase == "dispatch":
            self._cmd(out, self.guide, "goto", "manager")
        else:
            self._cmd(out, self.guide, "guide", "site")
        self._set_phase(out, phase)
        return out

    def _suspend(self, out, reason):
        self.resume_phase = self.phase
        self.hold = None
        if self.activity[self.guide] not in ("stopped", "estop"):
            self._cmd(out, self.guide, "stop")
        self._set_phase(out, "suspended")
        out.append(Notice("suspended", self.guide, {"reason": reason, "resume": self.resume_phase}))

    def _finish_return(self, out):
        if self.returning:
            return
        # 복귀를 마친 로봇만 순찰을 다시 시작합니다(그 사이 준비된 로봇은 사람 조작을 기다림).
        movers = sorted(self.returned & self.ready)
        for robot in movers:
            self._cmd(out, robot, "patrol")
        self._set_phase(out, "patrol" if movers else "standby")


def _robot(robot):
    if robot not in ROBOTS:
        raise ValueError("unknown robot")


def _other(robot):
    return "B" if robot == "A" else "A"


def _rejected(event, phase, **detail):
    return Notice("rejected", detail.pop("robot", None), {"event": event, "phase": phase, **detail})
