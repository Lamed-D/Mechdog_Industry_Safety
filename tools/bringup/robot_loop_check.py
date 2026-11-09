# Hiwonder.startMain 등록·양보 확인. 모션 객체·UART·Wi-Fi를 만들지 않습니다.


def run(allow_background=False, api=None, clock=None):
    if allow_background is not True:
        return {"status": "blocked"}
    if api is None:
        import Hiwonder as api
    if clock is None:
        import time as clock
    state = {"counts": [0] * 4, "done": [False] * 4, "errors": [None] * 4,
             "registration_error": None, "registration_elapsed_ms": None, "cancelled": False}

    def make_loop(index):
        def loop():
            if state["done"][index]:
                return
            try:
                for _ in range(50):
                    if state["cancelled"]:
                        break
                    state["counts"][index] += 1
                    clock.sleep_ms(10)
            except Exception as error:
                state["errors"][index] = type(error).__name__
            finally:
                state["done"][index] = True
        return loop

    started = clock.ticks_ms()
    try:
        for index in range(4):
            api.startMain(make_loop(index))
    except Exception as error:
        state["registration_error"] = type(error).__name__
        state["cancelled"] = True
    state["registration_elapsed_ms"] = clock.ticks_diff(clock.ticks_ms(), started)
    return state


if __name__ == "__main__":
    print("수동 루프 점검 파일입니다. import 후 run을 명시적으로 호출하세요.")
