# 사용자 REPL용: 객체 생성·후보 호출 없이 클래스의 속성 존재만 확인합니다.
# 존재해도 인자·단위·안전성 확인 전 사용하지 않습니다.
CANDIDATES = ("run_status", "wait_action_over", "read_servo", "read_all_servo",
              "read_offset", "set_offset", "save_offset", "set_angleoffset")


def inspect(dog_class):
    # 실물 MechDog 는 객체를 돌려주는 함수라 객체 생성 없이는 속성을 볼 수 없습니다. 그때는 None(확인 불가).
    if not isinstance(dog_class, type):
        return {name: None for name in CANDIDATES}
    return {name: callable(getattr(dog_class, name, None)) for name in CANDIDATES}


def main():
    from HW_MechDog import MechDog
    print(inspect(MechDog))
    print("presence only; no candidate invoked; signatures unverified; None = MechDog is a factory, not checked")


if __name__ == "__main__":
    main()
