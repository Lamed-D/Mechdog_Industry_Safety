# 사용자 수동 동작 점검. import/Download만으로 실행하지 않으며 main.py로 바꾸지 않습니다.
# 실제 관측 결과는 docs/user-tests/robot-python-checklist.md에 기록합니다.

MIN_BATTERY_MV = 7000  # 실측 전 가정. 본체 경고 기준과 동일
CASES = {"stop": (0, 0), "forward": (20, 0), "backward": (-20, 0),
         "left": (20, 5), "right": (20, -5), "action": None}


def _battery(api):
    value = api.Battery_power()
    if type(value) is not int or value < MIN_BATTERY_MV:
        raise ValueError("battery_unavailable_or_low")
    return value


def _wait(api, clock, duration_ms, done=None):
    started = clock.ticks_ms()
    last_battery = started
    while clock.ticks_diff(clock.ticks_ms(), started) < duration_ms:
        if clock.ticks_diff(clock.ticks_ms(), last_battery) >= 100:
            _battery(api)
            last_battery = clock.ticks_ms()
        if done is not None:
            value = done()
            if type(value) not in (bool, int) or value not in (0, 1):
                raise ValueError("invalid_action_completion")
            if value:
                return True
        clock.sleep_ms(20)
    return done is None


def run(case, allow_motion=False, api=None, dog_class=None, clock=None):
    """대상·주변 안전 확인 뒤 사용자가 한 항목씩 호출합니다. 소프트웨어 완료는 실물 합격이 아닙니다."""
    if case not in CASES:
        raise ValueError("unknown motion check")
    if allow_motion is not True:
        return {"status": "blocked", "reason": "explicit_motion_approval_required"}
    if api is None:
        import Hiwonder as api
    if dog_class is None:
        from HW_MechDog import MechDog as dog_class
    if clock is None:
        import time as clock
    dog, stage = None, "preflight"
    result = {"case": case, "status": "unknown", "observation_required": True}
    try:
        _battery(api)
        for name in ("move", "stop_action", "action_run", "action_is_over"):
            if not callable(getattr(dog_class, name, None)):
                raise ValueError("required_api_missing")
        stage = "construct"  # 생성 자체의 움직임도 실물 확인 대상
        dog = dog_class()
        stage = "initial_stop"
        dog.stop_action()
        dog.move(0, 0)
        stage = case
        if case == "action":
            dog.action_run("nodding_motion")
            _wait(api, clock, 200)  # 시작 직후 완료값을 믿지 않음
            if not _wait(api, clock, 3000, dog.action_is_over):
                raise ValueError("action_completion_timeout")
        else:
            dog.move(*CASES[case])
            _wait(api, clock, 300)
        result["status"] = "calls_completed"
    except Exception as error:
        result.update(stage=stage, error=type(error).__name__)
        known = ("battery_unavailable_or_low", "required_api_missing", "action_completion_timeout", "invalid_action_completion")
        result["reason"] = error.args[0] if error.args and error.args[0] in known else "api_call_failed"
    finally:
        if dog is not None:
            for name, args in (("stop_action", ()), ("move", (0, 0))):
                try:
                    getattr(dog, name)(*args)
                except Exception as error:
                    result.update(status="unknown")
                    result[name + "_stop_error"] = type(error).__name__
    return result


if __name__ == "__main__":
    print("수동 점검 파일입니다. 체크리스트 확인 후 import하여 run을 명시적으로 호출하세요.")
