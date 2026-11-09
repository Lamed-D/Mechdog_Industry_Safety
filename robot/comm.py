# Wi-Fi 접속과 명령·텔레메트리 UDP (docs/protocol.md 1·6절).
# 통신 전용 예외(docs/dev/mechdog-api.md 9절): network·socket 은 메시지를 주고받는 데만 쓰고 로봇을 움직이지 않습니다.

import netutil

MAX_DATAGRAM = 256
POLL_LIMIT = 8  # 한 번에 읽을 데이터그램 수 (다른 일을 막지 않게)


class Link:
    def __init__(self, cfg, network, socket, clock, ssid, password):
        self.cfg = cfg
        self.network = network
        self.socket = socket
        self.clock = clock
        self._ssid = ssid
        self._password = password
        self.wlan = None
        self.sock = None
        self.pm_on = False
        self._last_try = None

    def start(self):
        self.wlan = self.network.WLAN(self.network.STA_IF)
        self.wlan.active(True)
        try:
            # 절전 끄기: 펌웨어에 따라 없을 수 있음 [확인 필요]. 없으면 warn=pm_on
            self.wlan.config(pm=self.network.WLAN.PM_NONE)
            self.pm_on = False
        except Exception:
            self.pm_on = True
        self._try_connect()

    def _try_connect(self):
        self._last_try = self.clock.ticks_ms()
        if not self._ssid:
            return  # secrets.py 없음: 접속하지 않음(로봇은 래치 상태로 남음)
        try:
            self.wlan.connect(self._ssid, self._password)
        except Exception:
            pass

    def connected(self):
        try:
            return self.wlan is not None and bool(self.wlan.isconnected())
        except Exception:
            return False

    def service(self):
        """접속 상태를 보고 소켓을 열거나 닫고, 끊겼으면 일정 간격으로 다시 접속합니다."""
        if self.connected():
            if self.sock is None:
                self._open()
            return
        netutil.close(self.sock)
        self.sock = None
        if self.clock.ticks_diff(self.clock.ticks_ms(), self._last_try) >= self.cfg.WIFI_RETRY_MS:
            try:
                self.wlan.disconnect()
            except Exception:
                pass
            self._try_connect()

    def _open(self):
        sock = self.socket.socket(self.socket.AF_INET, self.socket.SOCK_DGRAM)
        try:
            sock.setsockopt(self.socket.SOL_SOCKET, self.socket.SO_REUSEADDR, 1)
            sock.bind(("0.0.0.0", self.cfg.CMD_PORT))
            sock.settimeout(0)
        except Exception:
            netutil.close(sock)
            return
        self.sock = sock

    def poll(self):
        """받은 (데이터, 주소) 목록. 받을 것이 없으면 빈 목록."""
        items = []
        while self.sock is not None and len(items) < POLL_LIMIT:
            try:
                items.append(self.sock.recvfrom(MAX_DATAGRAM))
            except OSError as error:
                if not netutil.no_data(error):
                    netutil.close(self.sock)  # 다음 service() 에서 다시 엶
                    self.sock = None
                break
        return items

    def send(self, line, dest):
        if self.sock is None or dest is None:
            return False
        try:
            self.sock.sendto(line.encode(), dest)
            return True
        except OSError:
            return False
