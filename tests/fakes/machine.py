"""가짜 `machine` 모듈: UART, Pin, unique_id.

`machine` 직접 사용은 추가 센서 읽기와 라이다 중계에만 허용됩니다(mechdog-api.md 6절, docs/protocol.md 7절).
UART는 MicroPython 표준 메서드(read, readinto, write, any)만 흉내 냅니다.
"""

from tests.fakes._base import FakeHardwareError

calls = []
uarts = []
_uart_error = [None]
_unique_id = [b"\x24\x0a\xc4\x00\x00\x01"]


def fake_reset():
    del calls[:]
    del uarts[:]
    _uart_error[0] = None
    _unique_id[0] = b"\x24\x0a\xc4\x00\x00\x01"


def fake_fail_uart(error):
    """다음 UART(...) 생성이 이 예외로 실패합니다(번호·키워드 미지원 흉내). None이면 해제."""
    _uart_error[0] = error


def fake_set_unique_id(value):
    _unique_id[0] = bytes(value)


def unique_id():
    calls.append(("unique_id", ()))
    return _unique_id[0]


class UART:
    def __init__(self, uart_id, baudrate=9600, rx=None, tx=None, rxbuf=256, **kwargs):
        calls.append(("UART", (uart_id, baudrate, rx, tx, rxbuf, dict(kwargs))))
        if _uart_error[0] is not None:
            raise _uart_error[0]
        if rxbuf <= 0:
            raise FakeHardwareError("UART: rxbuf %r" % (rxbuf,))
        self.uart_id = uart_id
        self.baudrate = baudrate
        self.rx = rx
        self.tx = tx
        self.rxbuf = rxbuf
        self.loopback = False  # True면 write한 바이트가 그대로 RX로 돌아옴(J5 TX-RX 연결 시험)
        self.dropped = 0       # RX 버퍼가 넘쳐 잃은 바이트 수
        self._rx = bytearray()
        self._tx = bytearray()
        uarts.append(self)

    def any(self):
        return len(self._rx)

    def read(self, nbytes=None):
        if not self._rx:
            return None  # MicroPython: 읽을 것이 없으면 None
        n = len(self._rx) if nbytes is None else min(nbytes, len(self._rx))
        data = bytes(self._rx[:n])
        del self._rx[:n]
        return data

    def readinto(self, buf, nbytes=None):
        data = self.read(len(buf) if nbytes is None else min(nbytes, len(buf)))
        if data is None:
            return None
        buf[:len(data)] = data
        return len(data)

    def write(self, buf):
        data = bytes(buf)
        self._tx.extend(data)
        if self.loopback:
            self.fake_feed(data)
        return len(data)

    # --- 테스트 도우미 (실제 API 아님) ---
    def fake_feed(self, data):
        """상대 장치(라이다)가 보낸 바이트. 버퍼를 넘는 만큼은 잃습니다."""
        room = self.rxbuf - len(self._rx)
        keep = bytes(data)[:max(room, 0)]
        self.dropped += len(data) - len(keep)
        self._rx.extend(keep)

    def fake_take_tx(self):
        data = bytes(self._tx)
        del self._tx[:]
        return data


class Pin:
    IN = 1
    OUT = 3
    PULL_UP = 1
    PULL_DOWN = 2

    def __init__(self, pin_id, mode=None, pull=None, value=None):
        calls.append(("Pin", (pin_id, mode, pull)))
        self.pin_id = pin_id
        self.mode = mode
        self._value = 0 if value is None else value

    def value(self, new=None):
        if new is None:
            return self._value
        self._value = 1 if new else 0
        return None
