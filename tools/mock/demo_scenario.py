"""실물·소켓·모델 없이 시나리오 전체를 가짜 시계로 실행하고 JSON Lines를 출력합니다."""
import argparse
import json

from dashboard.web.run import build_sim
from host.vision import EvidenceMonitor, Observation


def run_demo(finder="A", fault="none"):
    if finder not in ("A", "B") or fault not in ("none", "link", "camera", "estop"):
        raise ValueError("unknown synthetic demo option")
    now = [0.0]
    core, links = build_sim(clock=lambda: now[0], wall=lambda: 1700000000 + now[0])
    rows, pending = [], {}

    def record(event, detail=None):
        rows.append({"v": 1, "source": "synthetic", "simulation": True, "hardware": False,
                     "time_s": round(now[0], 3), "event": event, "phase": core.scenario.phase,
                     "detail": detail or {}})

    def commands():
        for robot in links:
            if links[robot].latched:
                pending.pop(robot, None)
        for command in core.drain_commands():
            record("command", {"robot": command.robot, "kind": command.kind, "arg": command.arg})
            if command.kind == "stop":
                pending.pop(command.robot, None)
            elif command.kind in ("goto", "guide"):
                pending[command.robot] = (command.arg, now[0] + .3)

    def tick():
        now[0] += .11
        for link in links.values():
            link.step()
        core.update()
        commands()
        for robot, (target, deadline) in list(pending.items()):
            if now[0] >= deadline and links[robot].online and not links[robot].latched:
                pending.pop(robot)
                core.arrived(robot, target)
                record("synthetic_arrival", {"robot": robot, "target": target})
                commands()

    def operator(event):
        result = core.operator(event)
        record("scripted_operator", {"event": event, "ok": result["ok"]})
        commands()

    def until(phase):
        for _ in range(100):
            if core.scenario.phase == phase:
                return
            tick()
        raise AssertionError("synthetic scenario did not reach " + phase)

    try:
        tick()
        record("boot")
        for robot in links:
            core.reset_latch(robot, confirmed=True)  # 합성 링크에 대한 연습용 사람 조작
            record("scripted_reset", {"robot": robot})
            core.camera_state(robot, {"status": "synthetic"})
        tick()
        operator("start_patrol")
        monitor = EvidenceMonitor(hold_s=.5)
        for _ in range(7):
            tick()
            core.detection(monitor.update(Observation(finder, now[0], .92, True, "synthetic"), now[0]))
            commands()
            record("synthetic_evidence")
        guide = core.scenario.guide
        if fault == "link":
            links[guide].online = False
            for _ in range(6):
                tick()
            links[guide].latched, links[guide].reason = True, "link_lost"
            record("link_lost")
            links[guide].online = True
            tick()
            core.reset_latch(guide, confirmed=True)
            record("scripted_reset", {"robot": guide})
            tick()
            operator("retry")
        elif fault == "camera":
            core.detection({"robot": guide, "status": "unknown", "reason": "synthetic_loss"})
            commands()
            record("camera_lost")
            core.detection({"robot": guide, "status": "unconfirmed", "source": "synthetic"})
            record("camera_restored")
            operator("retry")
        elif fault == "estop":
            core.estop_all(source="synthetic_operator")
            commands()
            record("estop")
            return {"simulation": True, "complete": False, "safely_stopped": True,
                    "phase": core.scenario.phase, "timeline": rows}
        until("at_manager")
        operator("operator_ack")
        operator("start_guide")
        until("on_site")
        operator("resolved")
        until("patrol")
        record("complete", {"alerts_resolved": all(a["state"] == "resolved" for a in core.alerts)})
        return {"simulation": True, "complete": True, "phase": core.scenario.phase, "timeline": rows}
    finally:
        core.log.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--finder", choices=("A", "B"), default="A")
    parser.add_argument("--fault", choices=("none", "link", "camera", "estop"), default="none")
    args = parser.parse_args()
    result = run_demo(args.finder, args.fault)
    for row in result.pop("timeline"):
        print(json.dumps(row, ensure_ascii=False))
    print(json.dumps({"event": "summary", **result}, ensure_ascii=False))


if __name__ == "__main__":
    main()
