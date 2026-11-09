"""가짜 모듈 공용 도구."""

import math


class FakeHardwareError(AssertionError):
    """문서 범위 밖 호출. 테스트 실패로 보이도록 AssertionError를 상속합니다."""


def check_int_range(name, value, low, high):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise FakeHardwareError("%s: 숫자가 아님 %r" % (name, value))
    if not math.isfinite(value) or not low <= value <= high:
        raise FakeHardwareError("%s: %r 가 범위 %d~%d 밖" % (name, value, low, high))


def check_vec3(name, value):
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise FakeHardwareError("%s: 숫자 3개 리스트가 아님 %r" % (name, value))
    for item in value:
        if isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(item):
            raise FakeHardwareError("%s: 유한한 숫자가 아님 %r" % (name, value))


def outcome(value):
    """주입한 값을 돌려주거나, 예외 객체면 그 예외를 일으킵니다(읽기 실패 흉내)."""
    if isinstance(value, BaseException):
        raise value
    return value
