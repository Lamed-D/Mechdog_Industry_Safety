"""MicroPython `time`의 ticks 함수를 흉내 내는 가짜 시계.

CPython `time`에는 ticks_ms·ticks_diff·sleep_ms가 없고, 테스트 도구도 진짜 `time`을 쓰므로
sys.modules를 바꾸지 않고 이 객체를 로봇 코드에 넘겨 씁니다. 시간은 sleep·advance로만 흐릅니다.

ticks 값은 MicroPython처럼 일정 주기(TICKS_PERIOD)로 넘쳐 0으로 돌아갑니다. 넘침 직전에서 시작해
ticks_diff를 쓰지 않은 코드(단순 뺄셈)를 잡아낼 수 있습니다.
"""

TICKS_PERIOD = 1 << 30
TICKS_MAX = TICKS_PERIOD - 1
_TICKS_HALF = TICKS_PERIOD // 2


class FakeClock:
    def __init__(self, start_ms=0):
        self.now_ms = start_ms  # 넘치지 않는 실제 경과 시간
        self.sleeps = []        # sleep 호출 기록(ms)

    def advance(self, ms):
        if ms < 0:
            raise ValueError("시간은 거꾸로 가지 않음")
        self.now_ms += ms

    # --- MicroPython time 과 같은 이름 ---
    def ticks_ms(self):
        return int(self.now_ms) & TICKS_MAX

    def ticks_add(self, ticks, delta):
        return (ticks + delta) & TICKS_MAX

    def ticks_diff(self, ticks1, ticks2):
        return ((ticks1 - ticks2 + _TICKS_HALF) & TICKS_MAX) - _TICKS_HALF

    def sleep_ms(self, ms):
        self.sleeps.append(ms)
        self.advance(ms)

    def sleep(self, seconds):
        ms = seconds * 1000
        self.sleeps.append(ms)
        self.advance(ms)

    def time(self):
        return int(self.now_ms // 1000)
