"""가짜 `Hiwonder` 모듈: startMain, Buzzer, Button, Battery_power.

`startMain`은 함수를 등록만 하고 실행하지 않습니다. 테스트가 `main_funcs`의 함수를 직접(또는 한 단계씩) 부릅니다.
"""

from tests.fakes._base import FakeHardwareError, check_int_range, outcome

DEFAULT_BATTERY_MV = 7800

calls = []
main_funcs = []
buttons = []
_battery = [DEFAULT_BATTERY_MV]


def fake_reset():
    del calls[:]
    del main_funcs[:]
    del buttons[:]
    _battery[0] = DEFAULT_BATTERY_MV


def fake_set_battery(value):
    """다음 Battery_power() 결과. 정수(mV), None, 또는 예외 객체(읽기 실패)."""
    _battery[0] = value


def startMain(func):
    if not callable(func):
        raise FakeHardwareError("startMain: 함수가 아님 %r" % (func,))
    calls.append(("startMain", (func,)))
    main_funcs.append(func)


def Battery_power():
    # 제조사 예제 기준 mV 정수 (docs/protocol.md 5.4절)
    calls.append(("Battery_power", ()))
    return outcome(_battery[0])


class Buzzer:
    def __init__(self):
        calls.append(("Buzzer", ()))

    def playTone(self, freq, duration, wait):
        check_int_range("playTone freq", freq, 1, 20000)
        check_int_range("playTone duration", duration, 0, 60000)
        if not isinstance(wait, bool):
            raise FakeHardwareError("playTone wait: True/False 가 아님 %r" % (wait,))
        calls.append(("playTone", (freq, duration, wait)))


class Button:
    def __init__(self, number):
        calls.append(("Button", (number,)))
        self.number = number
        self.callback = None
        buttons.append(self)

    def Clicked(self, callback):
        if not callable(callback):
            raise FakeHardwareError("Clicked: 함수가 아님 %r" % (callback,))
        calls.append(("Clicked", (self.number,)))
        self.callback = callback

    def fake_click(self):
        if self.callback is not None:
            self.callback()
