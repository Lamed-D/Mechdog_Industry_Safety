"""가짜 `Hiwonder_IIC` 모듈: IIC, MPU(read_angle), I2CSonar."""

from tests.fakes._base import FakeHardwareError, check_int_range, outcome

calls = []
_angle = [[0.0, 0.0]]
_distance_cm = [100]


def fake_reset():
    del calls[:]
    _angle[0] = [0.0, 0.0]
    _distance_cm[0] = 100


def fake_set_angle(value):
    """다음 read_angle() 결과. 제조사 예제는 [0]·[1]만 씀. None·예외 객체로 실패를 흉내 냅니다."""
    _angle[0] = value


def fake_set_distance(value):
    """다음 getDistance() 결과(cm로 보임, mechdog-api.md 3절). None·예외 객체로 실패를 흉내 냅니다."""
    _distance_cm[0] = value


class IIC:
    def __init__(self, bus, mode=None):
        # 제조사 예제에 IIC(1), IIC(2), IIC(2, mode=1) 이 보임. mode 의미는 미기재.
        if bus not in (1, 2):
            raise FakeHardwareError("IIC: 버스 번호 %r (예제는 1·2만)" % (bus,))
        calls.append(("IIC", (bus, mode)))
        self.bus = bus
        self.mode = mode


class MPU:
    def __init__(self, iic=None):
        # 제조사 예제에 MPU()와 MPU(iic) 둘 다 보임.
        if iic is not None and not isinstance(iic, IIC):
            raise FakeHardwareError("MPU: IIC 객체가 아님 %r" % (iic,))
        calls.append(("MPU", (iic,)))

    def read_angle(self):
        calls.append(("read_angle", ()))
        value = outcome(_angle[0])
        return list(value) if value is not None else None


class I2CSonar:
    def __init__(self, iic):
        if not isinstance(iic, IIC):
            raise FakeHardwareError("I2CSonar: IIC 객체가 아님 %r" % (iic,))
        calls.append(("I2CSonar", (iic.bus,)))

    def getDistance(self):
        calls.append(("getDistance", ()))
        return outcome(_distance_cm[0])

    def setRGB(self, n, r, g, b):
        for name, value in (("r", r), ("g", g), ("b", b)):
            check_int_range("setRGB " + name, value, 0, 255)
        calls.append(("setRGB", (n, r, g, b)))
