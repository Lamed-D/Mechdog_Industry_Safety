"""MicroPython `socket` 일부를 흉내 내는 메모리 안 가짜 네트워크.

로봇 코드에는 `FakeNet()` 객체를 `socket` 모듈 대신 넘깁니다(같은 이름의 상수·socket() 제공).
가짜는 기다리지 않습니다: 받을 것이 없으면 시간 제한과 상관없이 바로 OSError(EAGAIN 또는 ETIMEDOUT)를 냅니다.
테스트 쪽(Pi 5 흉내)은 `net.peer(...)`로 상대 소켓을 만들거나 `net.deliver_udp(...)`로 데이터그램을 넣습니다.
"""

import errno

AF_INET = 2
SOCK_STREAM = 1
SOCK_DGRAM = 2
SOL_SOCKET = 0xFFF
SO_REUSEADDR = 4


class FakeNet:
    AF_INET = AF_INET
    SOCK_STREAM = SOCK_STREAM
    SOCK_DGRAM = SOCK_DGRAM
    SOL_SOCKET = SOL_SOCKET
    SO_REUSEADDR = SO_REUSEADDR

    def __init__(self, robot_ip="192.168.4.20"):
        self.robot_ip = robot_ip
        self.bound = {}       # port -> socket (UDP 수신, TCP 서버)
        self.sockets = []
        self.udp_sent = []    # (보낸 소켓 포트, (ip, port), bytes)
        self.down = False     # True면 보내기가 OSError (Wi-Fi 끊김 흉내)

    def socket(self, family=AF_INET, kind=SOCK_STREAM, *args):
        sock = FakeSocket(self, kind)
        self.sockets.append(sock)
        return sock

    def getaddrinfo(self, host, port, *args):
        return [(AF_INET, SOCK_STREAM, 0, "", (host, port))]

    # --- 테스트 도우미 ---
    def deliver_udp(self, port, data, src=("192.168.4.10", 50000)):
        sock = self.bound.get(port)
        if sock is None or sock.closed:
            return False  # 받는 쪽이 없으면 UDP처럼 조용히 사라짐
        sock.inbox.append((bytes(data), src))
        return True

    def connect_tcp(self, port, src=("192.168.4.10", 50001)):
        """Pi 5 쪽 TCP 클라이언트가 로봇 서버에 연결합니다. 클라이언트 쪽 소켓을 돌려줍니다."""
        server = self.bound.get(port)
        if server is None or server.closed or not server.listening:
            raise OSError(errno.ECONNREFUSED, "connection refused")
        client = FakeSocket(self, SOCK_STREAM)
        accepted = FakeSocket(self, SOCK_STREAM)
        client.peer, accepted.peer = accepted, client
        client.connected = accepted.connected = True
        server.pending.append((accepted, src))
        self.sockets.extend([client, accepted])
        return client


class FakeSocket:
    def __init__(self, net, kind):
        self.net = net
        self.kind = kind
        self.port = None
        self.timeout = None
        self.closed = False
        self.listening = False
        self.connected = False
        self.peer = None
        self.options = {}
        self.inbox = []        # UDP: (bytes, addr)
        self.stream = bytearray()  # TCP 수신 바이트
        self.pending = []      # TCP 서버: 받지 않은 연결

    def _check_open(self):
        if self.closed:
            raise OSError(errno.EBADF, "closed")

    def _empty(self):
        code = errno.EAGAIN if self.timeout == 0 else errno.ETIMEDOUT
        raise OSError(code, "no data")

    def setsockopt(self, level, option, value):
        self.options[(level, option)] = value

    def settimeout(self, seconds):
        self.timeout = seconds

    def setblocking(self, flag):
        self.timeout = None if flag else 0

    def bind(self, addr):
        self._check_open()
        port = addr[1]
        other = self.net.bound.get(port)
        if other is not None and not other.closed:
            raise OSError(errno.EADDRINUSE, "address in use")
        self.port = port
        self.net.bound[port] = self

    def listen(self, backlog=1):
        self.listening = True

    def accept(self):
        self._check_open()
        if not self.pending:
            self._empty()
        return self.pending.pop(0)

    # --- UDP ---
    def recvfrom(self, size):
        self._check_open()
        if not self.inbox:
            self._empty()
        data, addr = self.inbox.pop(0)
        return data[:size], addr

    def sendto(self, data, addr):
        self._check_open()
        if self.net.down:
            raise OSError(errno.EHOSTUNREACH, "network down")
        self.net.udp_sent.append((self.port, tuple(addr), bytes(data)))
        return len(data)

    # --- TCP ---
    def recv(self, size):
        self._check_open()
        if not self.stream:
            if self.peer is None or self.peer.closed:
                return b""  # 상대가 닫음
            self._empty()
        data = bytes(self.stream[:size])
        del self.stream[:size]
        return data

    def send(self, data):
        self._check_open()
        if self.net.down or self.peer is None or self.peer.closed:
            raise OSError(errno.ECONNRESET, "connection reset")
        self.peer.stream.extend(bytes(data))
        return len(data)

    def sendall(self, data):
        self.send(data)

    def write(self, data):
        return self.send(data)

    def close(self):
        self.closed = True
        if self.net.bound.get(self.port) is self:
            del self.net.bound[self.port]
