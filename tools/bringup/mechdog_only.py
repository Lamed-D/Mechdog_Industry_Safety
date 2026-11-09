# 지금 보유한 MechDog만으로 수행하는 읽기 점검. 실행은 사용자 승인 후 REPL에서 합니다.
# MechDog 객체를 만들지 않으며 UART·네트워크·모터를 건드리지 않습니다.


def inspect(api, dog_class):
    methods = ("move", "action_run", "stop_action", "action_is_over", "set_default_pose")
    supported = {name: callable(getattr(dog_class, name, None)) for name in methods}
    try:
        battery = api.Battery_power()
        if isinstance(battery, bool) or not isinstance(battery, int) or battery <= 0:
            battery = None
    except Exception:
        battery = None
    return {"api": supported, "battery_mv": battery, "hardware_motion_tested": False}


def main():
    import Hiwonder
    from HW_MechDog import MechDog
    result = inspect(Hiwonder, MechDog)
    print(result)
    return result


if __name__ == "__main__":
    main()
