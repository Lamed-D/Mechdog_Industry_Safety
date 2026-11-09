"""가짜 `network` 모듈: WLAN(STA_IF) 접속·끊김, 절전 끄기(PM_NONE) 지원 여부.

Wi-Fi는 Pi 5와 통신하는 데만 씁니다(mechdog-api.md 9절). 펌웨어에 따라 `WLAN.PM_NONE`이 없을 수 있어
(docs/protocol.md 6.1절 `pm_on`) `fake_set_pm_supported(False)`로 그 상황을 만듭니다.
"""

STA_IF = 0
AP_IF = 1

FAKE_IP = "192.168.4.20"
_NO_IP = ("0.0.0.0", "0.0.0.0", "0.0.0.0", "0.0.0.0")

calls = []
wlans = []
_ap_available = [True]


def fake_reset():
    del calls[:]
    del wlans[:]
    _ap_available[0] = True
    fake_set_pm_supported(True)


def fake_set_ap(available):
    """공유기가 있는지. False면 connect()해도 붙지 않습니다."""
    _ap_available[0] = available


def fake_set_pm_supported(supported):
    for name, value in (("PM_NONE", 0), ("PM_PERFORMANCE", 1), ("PM_POWERSAVE", 2)):
        if supported:
            setattr(WLAN, name, value)
        elif hasattr(WLAN, name):
            delattr(WLAN, name)


class WLAN:
    def __init__(self, interface=STA_IF):
        calls.append(("WLAN", (interface,)))
        self.interface = interface
        self._active = False
        self._connected = False
        self.ssid = None
        self.pm = None
        wlans.append(self)

    def active(self, is_active=None):
        if is_active is None:
            return self._active
        calls.append(("active", (is_active,)))
        self._active = bool(is_active)
        if not self._active:
            self._connected = False
        return None

    def connect(self, ssid=None, key=None):
        # 비밀번호는 기록하지 않습니다.
        calls.append(("connect", (ssid,)))
        if not self._active:
            raise OSError("Wifi Not Started")
        self.ssid = ssid
        self._connected = _ap_available[0]

    def disconnect(self):
        calls.append(("disconnect", ()))
        self._connected = False

    def isconnected(self):
        return self._connected

    def ifconfig(self):
        if not self._connected:
            return _NO_IP
        return (FAKE_IP, "255.255.255.0", "192.168.4.1", "192.168.4.1")

    def config(self, *args, **kwargs):
        calls.append(("config", (args, dict(kwargs))))
        if "pm" in kwargs:
            if not hasattr(WLAN, "PM_NONE"):
                raise ValueError("unknown config param")
            self.pm = kwargs["pm"]
        return None

    # --- 테스트 도우미 (실제 API 아님) ---
    def fake_drop(self):
        """공유기와 연결이 끊긴 상황."""
        self._connected = False


fake_set_pm_supported(True)
