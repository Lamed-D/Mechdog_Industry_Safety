# RPLIDAR A1M8-R6 원시 중계: J5 UART <-> TCP (docs/protocol.md 7절, docs/lidar-integration.md 6.2절 A안).
# 라이다 바이트를 해석·가공하지 않고 같은 순서로 넘깁니다. 로봇을 움직이지 않으며 안전 래치와 무관합니다.
# machine.UART 직접 사용은 추가 센서 예외(docs/dev/mechdog-api.md 6절): 공식 UART 는 텍스트 명령용이라 바이너리를 못 다룸.
# 통신 값(115200 bps 8N1, 3.3 V TTL)은 공개 데이터시트 기준. J5: IO32 = 로봇 RX, IO33 = 로봇 TX (방향 [확인 필요]).

import errno

CHUNK = 512      # 한 번에 UART 에서 읽는 최대 바이트
RECV_SIZE = 64   # Pi 5 -> 라이다 명령은 짧음
DRAIN_MAX = 16   # 한 번에 버리는 최대 묶음 수 (다른 일을 막지 않게)

_NO_DATA = [errno.EAGAIN, errno.ETIMEDOUT]
if hasattr(errno, "EWOULDBLOCK"):
    _NO_DATA.append(errno.EWOULDBLOCK)


def _no_data(error):
    code = getattr(error, "errno", None)
    if code is None and error.args:
        code = error.args[0]
    return code in _NO_DATA


def _close(sock):
    if sock is not None:
        try:
            sock.close()
        except Exception:
            pass


class LidarBridge:
    def __init__(self, cfg, machine, socket, clock=None):
        self.cfg = cfg
        self.socket = socket
        self.clock = clock
        self.waiting = self.high_water = self.drained = self.stalls = 0
        self._pending_since = None
        self._rate_at = clock.ticks_ms() if clock is not None else None
        self._rate_sent = self._rate_received = 0
        self.send_bps = self.receive_bps = None
        self.uart = None
        self.server = None
        self.conn = None
        self.pending = b""     # 라이다 -> Pi 5 로 아직 못 보낸 바이트
        self.tx_pending = b""  # Pi 5 -> 라이다 로 아직 못 쓴 바이트
        self.sent = 0       # 라이다 -> Pi 5 바이트 수
        self.received = 0   # Pi 5 -> 라이다 바이트 수
        try:
            self.uart = machine.UART(cfg.LIDAR_UART_ID, baudrate=cfg.LIDAR_BAUD,
                                     rx=cfg.LIDAR_RX_PIN, tx=cfg.LIDAR_TX_PIN, rxbuf=cfg.LIDAR_RXBUF)
        except Exception:
            self.uart = None  # 번호·키워드 미지원 [확인 필요] -> warn=lidar_uart

    def uart_ok(self):
        return self.uart is not None

    def service(self, network_up):
        """중계를 한 단계 진행합니다. 짧은 주기로 반복해 부릅니다."""
        if not network_up:
            self.stop()
            return
        if self.server is None:
            self._open_server()
        self._accept()
        if self.conn is None:
            self._drain()
            return
        self.waiting = self.uart.any()
        self.high_water = max(self.high_water, self.waiting)
        self._to_pi()
        if self.conn is not None:
            self._to_lidar()
        if self.conn is not None:
            self._sample_rate()

    def _sample_rate(self):
        if self.clock is None:
            return
        now = self.clock.ticks_ms()
        elapsed = self.clock.ticks_diff(now, self._rate_at)
        if elapsed >= 1000:
            self.send_bps = (self.sent - self._rate_sent) * 1000 // elapsed
            self.receive_bps = (self.received - self._rate_received) * 1000 // elapsed
            self._rate_at = now
            self._rate_sent, self._rate_received = self.sent, self.received

    def _pending_age(self):
        if self.clock is not None and self._pending_since is not None:
            return max(0, self.clock.ticks_diff(self.clock.ticks_ms(), self._pending_since))
        return None

    def metrics(self):
        return {"connected": self.conn is not None, "uart_waiting": self.waiting,
                "uart_high_water": self.high_water, "pending_bytes": len(self.pending),
                "pending_age_ms": self._pending_age(), "sent": self.sent, "received": self.received,
                "drained": self.drained, "stalls": self.stalls,
                "send_bps": self.send_bps, "receive_bps": self.receive_bps}

    def backlogged(self):
        age = self._pending_age()
        return self.conn is not None and (self.waiting * 4 >= self.cfg.LIDAR_RXBUF * 3
                or (age is not None and age >= self.cfg.LIDAR_PENDING_WARN_MS))

    def stop(self):
        self._drop()
        _close(self.server)
        self.server = None

    def _open_server(self):
        server = self.socket.socket(self.socket.AF_INET, self.socket.SOCK_STREAM)
        try:
            server.setsockopt(self.socket.SOL_SOCKET, self.socket.SO_REUSEADDR, 1)
            server.bind(("0.0.0.0", self.cfg.LIDAR_TCP_PORT))
            server.listen(1)
            server.settimeout(0)
        except Exception:
            _close(server)
            return
        self.server = server

    def _accept(self):
        if self.server is None:
            return
        try:
            conn, _addr = self.server.accept()
        except OSError:
            return  # 기다리는 연결 없음
        if self.uart is None:
            _close(conn)  # UART 를 못 열었으면 받자마자 닫음
            return
        self._drop()  # 한 번에 하나: 새 연결이 옛 연결을 대신함
        conn.settimeout(0)
        self.conn = conn
        self._drain()  # 연결 전에 쌓인 오래된 바이트는 보내지 않음

    def _drop(self):
        _close(self.conn)
        self.conn = None
        self.pending = b""
        self.tx_pending = b""
        self.waiting = 0
        self._pending_since = None
        self.send_bps = self.receive_bps = None
        if self.clock is not None:
            self._rate_at = self.clock.ticks_ms()
            self._rate_sent, self._rate_received = self.sent, self.received

    def _drain(self):
        if self.uart is None:
            return
        for _ in range(DRAIN_MAX):
            if not self.uart.any():
                break
            data = self.uart.read(CHUNK)
            if not data:
                break
            self.drained += len(data)

    def _to_pi(self):
        if not self.pending:
            waiting = self.waiting
            if waiting:
                self.pending = self.uart.read(min(waiting, CHUNK)) or b""
                if self.pending and self.clock is not None:
                    self._pending_since = self.clock.ticks_ms()
        if not self.pending:
            return
        try:
            count = self.conn.send(self.pending)
        except OSError as error:
            self.stalls += 1
            if not _no_data(error):
                self._drop()
            return
        count = count or 0
        if not count:
            self.stalls += 1
        self.sent += count
        self.pending = self.pending[count:]  # 못 보낸 바이트는 다음에 (UART 는 그동안 버퍼에 쌓임)
        if not self.pending:
            self._pending_since = None

    def _to_lidar(self):
        # 못 쓴 바이트를 먼저 순서대로 다 쓴 뒤에만 다음 TCP 데이터를 읽음(명령 경계 유지)
        if not self.tx_pending:
            try:
                data = self.conn.recv(RECV_SIZE)
            except OSError as error:
                if not _no_data(error):
                    self._drop()
                return
            if not data:
                self._drop()  # 상대가 닫음. 라이다에는 아무것도 보내지 않음
                return
            self.tx_pending = data
        try:
            count = self.uart.write(self.tx_pending)
        except Exception:
            self._drop()
            return
        count = count or 0  # None(시간 초과)·0 이면 다음에 다시
        self.received += count
        self.tx_pending = self.tx_pending[count:]
