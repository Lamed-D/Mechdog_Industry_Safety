"""대시보드 핵심 상태와 사람 조작 (WP-D2). 웹·네트워크 없이 테스트할 수 있는 순수 로직.

연결 대상
- scenario: scenario.machine.Scenario
- links: {"A": link, "B": link}. link 는 host.robot_link.RobotLink 와 같은 모양
  (estop(), request_reset(), fresh(), status(), latest, 선택 step()).
- log: dashboard.core.log.EventLog

안전 원칙
- 전체 정지는 확인 없이 바로, 모든 링크에 먼저 보냅니다. 링크 하나·시나리오·기록이 실패해도 나머지는 계속합니다.
- 래치 해제는 확인(confirmed=True)을 거친 사람 조작으로만 합니다. 자동 해제는 없습니다.
- 텔레메트리가 끊기거나 로봇이 래치되면 시나리오의 준비 상태에서 뺍니다(그 로봇에 이동을 맡기지 않음).
- 이동 명령(patrol·goto·guide·action·pose)은 여기서 실행하지 않고 어댑터(WP-D3)가 가져갑니다.
"""
from collections import deque
import time

ROBOTS = ("A", "B")
OPERATOR_EVENTS = ("start_patrol", "operator_ack", "start_guide", "retry", "resolved", "guide_clear")


class DashboardCore:
    def __init__(self, scenario, links, log, clock=time.monotonic, wall=time.time, notice_limit=100):
        self.scenario = scenario
        self.links = dict(links)
        self.log = log
        self.clock = clock
        self.wall = wall
        self.robots = {r: {"link": "unknown", "fresh": False, "state": "unknown", "latched": None,
                           "reason": None, "battery_mv": None, "warnings": [], "last_seen_age_s": None,
                           "camera": "unknown"} for r in ROBOTS}
        self.alerts = []
        self.notices = deque(maxlen=notice_limit)
        self.commands = deque()
        self._was_fresh = {r: False for r in ROBOTS}
        self._ready = {r: False for r in ROBOTS}

    # ---- 사람 조작 ---------------------------------------------------------
    def estop_all(self, source="operator"):
        """전체 정지. 반환값의 errors 가 비어 있지 않으면 화면에 크게 알려야 합니다."""
        sent, errors = [], []
        for robot in ROBOTS:
            link = self.links.get(robot)
            if link is None:
                errors.append({"robot": robot, "error": "no_link"})
                continue
            try:
                link.estop()
                sent.append(robot)
            except Exception as error:
                errors.append({"robot": robot, "error": type(error).__name__})
                continue
            self._push_now(link, robot, errors)
        try:
            self._apply(self.scenario.estop_all())
        except Exception as error:
            errors.append({"robot": None, "error": "scenario_" + type(error).__name__})
        self._log("estop_all", None, {"source": source, "sent": sent, "errors": errors})
        return {"ok": not errors, "sent": sent, "errors": errors}

    def reset_latch(self, robot, confirmed=False):
        """래치 해제 요청. 확인 창을 거친 조작만. 실제 해제 여부는 로봇 텔레메트리로 판단합니다."""
        if robot not in ROBOTS:
            raise ValueError("unknown robot")
        if not confirmed:
            return self._rejected("reset_latch", robot, "confirmation_required")
        link = self.links.get(robot)
        if link is None:
            return self._rejected("reset_latch", robot, "no_link")
        try:
            link.request_reset()
        except ValueError as error:
            return self._rejected("reset_latch", robot, str(error))
        self._log("reset_requested", robot, {})
        return {"ok": True}

    def operator(self, event):
        """알림 확인·안내 시작·조치 완료 등 확인 없이 되는 사람 조작."""
        if event not in OPERATOR_EVENTS:
            raise ValueError("unknown operator event")
        out = getattr(self.scenario, event)()
        self._log("operator", None, {"event": event})
        self._apply(out)
        return self._result(out)

    def guide_blocked(self, reason):
        out = self.scenario.guide_blocked(str(reason))
        self._apply(out)
        return self._result(out)

    # ---- 외부 입력 ---------------------------------------------------------
    def detection(self, result, zone=None):
        """host.vision.EvidenceMonitor 결과."""
        self._apply(self.scenario.detection(result, zone))

    def arrived(self, robot, target):
        self._apply(self.scenario.arrived(robot, target))

    def camera_state(self, robot, state):
        """영상 수신기 state() 결과. 영상이 없으면 감지 불가로 표시합니다."""
        if robot not in ROBOTS:
            raise ValueError("unknown robot")
        self.robots[robot]["camera"] = state.get("status", "unknown") if isinstance(state, dict) else "unknown"

    def update(self):
        """10Hz 안팎으로 호출. 링크 상태를 읽어 시나리오에 준비·끊김을 알리고 시간 초과를 처리합니다."""
        for robot in ROBOTS:
            self._update_robot(robot)
        self._apply(self.scenario.tick())

    def drain_commands(self):
        """어댑터가 실행할 이동 명령(scenario.machine.Command)들."""
        out = list(self.commands)
        self.commands.clear()
        return out

    def snapshot(self):
        return {"phase": self.scenario.phase, "scenario": self.scenario.snapshot(),
                "robots": {r: dict(v) for r, v in self.robots.items()},
                "alerts": [dict(a) for a in self.alerts], "notices": list(self.notices),
                "log_failures": getattr(self.log, "failures", 0)}

    # ---- 내부 --------------------------------------------------------------
    def _update_robot(self, robot):
        view = self.robots[robot]
        link = self.links.get(robot)
        fresh, latest, status = False, None, "unknown"
        if link is not None:
            try:
                fresh = bool(link.fresh())
                status = link.status()
                latest = link.latest
            except Exception:
                fresh, latest, status = False, None, "unknown"
        view.update(link="ok" if fresh else ("stale" if status != "unknown" else "unknown"),
                    fresh=fresh, state=status)
        if latest is not None:
            view.update(latched=latest.latched, reason=latest.reason, battery_mv=latest.battery_mv,
                        warnings=sorted(latest.warnings))
        last_seen = getattr(link, "last_seen", None) if link is not None else None
        view["last_seen_age_s"] = (round(self.clock() - last_seen, 2)
                                   if isinstance(last_seen, (int, float)) and last_seen > -1e300 else None)

        if self._was_fresh[robot] and not fresh:
            self._ready[robot] = False
            self._apply(self.scenario.link_lost(robot))
        elif fresh and latest is not None and latest.latched and self._ready[robot]:
            # 로봇이 스스로 래치(저전압·감시 타이머 등)되면 준비 상태에서 뺍니다.
            self._ready[robot] = False
            self._note("robot_latched", robot, {"reason": latest.reason})
            self._apply(self.scenario.link_lost(robot))
        elif fresh and latest is not None and not latest.latched and not self._ready[robot]:
            self._ready[robot] = True
            self._apply(self.scenario.robot_ready(robot))
        self._was_fresh[robot] = fresh

    def _push_now(self, link, robot, errors):
        step = getattr(link, "step", None)
        if callable(step):
            try:
                step()
            except Exception as error:
                errors.append({"robot": robot, "error": "send_" + type(error).__name__})

    def _apply(self, out):
        for item in out:
            if hasattr(item, "kind") and hasattr(item, "arg"):   # Command
                if item.kind == "estop":
                    link = self.links.get(item.robot)
                    if link is not None:
                        try:
                            link.estop()
                        except Exception:
                            self._note("estop_failed", item.robot, {})
                else:
                    self.commands.append(item)
            else:                                                # Notice
                self._notice(item)

    def _notice(self, notice):
        detail = dict(notice.detail)
        self._note(notice.kind, notice.robot, detail)
        if notice.kind == "alert":
            self.alerts.append({**detail, "state": "open", "wall_time": self.wall()})
        elif notice.kind in ("alert_update", "alert_acked", "resolved"):
            for alert in self.alerts:
                if alert.get("id") == detail.get("id"):
                    if notice.kind == "alert_update":
                        alert.update({k: v for k, v in detail.items() if k != "acked"})
                    elif notice.kind == "alert_acked":
                        alert["acked"] = True
                    else:
                        alert["state"] = "resolved"

    def _note(self, kind, robot, detail):
        self.notices.append({"kind": kind, "robot": robot, "detail": detail, "wall_time": self.wall()})
        self._log(kind, robot, detail)

    def _log(self, kind, robot, detail):
        try:
            self.log.record(kind, robot, detail)
        except Exception:
            pass   # 기록 실패가 조작을 막지 않게 함 (EventLog 는 실패 횟수를 셈)

    def _rejected(self, event, robot, reason):
        self._note("rejected", robot, {"event": event, "reason": reason})
        return {"ok": False, "reason": reason}

    @staticmethod
    def _result(out):
        rejected = [n for n in out if getattr(n, "kind", None) == "rejected"]
        if rejected:
            return {"ok": False, "reason": rejected[0].detail}
        return {"ok": True}
