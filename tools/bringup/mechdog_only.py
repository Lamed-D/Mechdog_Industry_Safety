# 지금 보유한 MechDog만으로 수행하는 읽기 점검. 실행은 사용자 승인 후 REPL에서 합니다.
# MechDog 객체를 만들지 않으며 UART·네트워크·모터를 건드리지 않습니다.


METHODS = ("move", "action_run", "stop_action", "action_is_over", "set_default_pose")


def inspect(api, dog_class):
    # 실물 본체(로봇 B)의 HW_MechDog.MechDog 는 클래스가 아니라 객체를 돌려주는 함수였습니다
    # (type 이 function, dir 은 __class__·__name__·__globals__ 뿐). 함수에서는 메서드를 찾을 수 없으므로
    # 객체를 만들지 않는 이 점검에서는 "확인 불가"로 남기고 False(없음)로 단정하지 않습니다.
    if isinstance(dog_class, type):
        supported = {name: callable(getattr(dog_class, name, None)) for name in METHODS}
        kind = "class"
    else:
        supported = {name: None for name in METHODS}
        kind = "factory" if callable(dog_class) else "missing"
    try:
        battery = api.Battery_power()
        if isinstance(battery, bool) or not isinstance(battery, int) or battery <= 0:
            battery = None
    except Exception:
        battery = None
    # api 값: True/False=클래스에서 확인, None=객체 생성 전이라 확인 불가(factory)
    return {"api": supported, "mechdog_kind": kind, "battery_mv": battery, "hardware_motion_tested": False}


def main():
    import Hiwonder
    from HW_MechDog import MechDog
    result = inspect(Hiwonder, MechDog)
    print(result)
    return result


if __name__ == "__main__":
    main()
