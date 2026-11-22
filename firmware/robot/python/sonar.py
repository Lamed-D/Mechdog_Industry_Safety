# 초음파 센서(공식 Hiwonder_IIC.I2CSonar) 거리 읽기와 RGB LED 색. 로봇을 움직이지 않습니다.
# 근거: 제조사 예제 - IIC(1) 에 I2CSonar, getDistance() 값을 cm 로 쓰고(앱에 *10 해서 mm 로 보냄),
# setRGB(0, r, g, b) 로 두 LED 색을 바꿈. getDistance 단위·범위는 실물 확인 필요(ai/mechdog-api.md 3.2절).
# 읽기 실패·범위 밖은 None 이며 "장애물 없음"으로 바꾸지 않습니다(ai/mechdog-api.md 8절).

MIN_MM = 20      # [가정] 이보다 가까운 값은 측정 무효로 봄
MAX_MM = 5000    # [가정] 이보다 먼 값은 측정 무효로 봄


def _channel(value):
    value = int(value)
    if not 0 <= value <= 255:
        raise ValueError("rgb 0..255")
    return value


class Sonar:
    def __init__(self, api, iic):
        self.device = None
        self.error = None
        try:
            self.device = api.I2CSonar(iic)
        except Exception:
            self.error = "sonar_init_failed"

    def read_mm(self):
        """거리(mm, 정수) 또는 None."""
        if self.device is None:
            return None
        try:
            cm = self.device.getDistance()
        except Exception:
            return None
        if isinstance(cm, bool) or not isinstance(cm, (int, float)):
            return None
        mm = int(round(cm * 10))
        if not MIN_MM <= mm <= MAX_MM:
            return None
        return mm

    def set_rgb(self, r, g, b):
        """두 LED(인덱스 0)를 같은 색으로. 성공하면 True."""
        if self.device is None:
            return False
        try:
            self.device.setRGB(0, _channel(r), _channel(g), _channel(b))
            return True
        except Exception:
            return False
