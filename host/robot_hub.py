"""두 로봇의 공통 TEL 포트를 소켓 하나로 받습니다. 생성할 때만 네트워크를 엽니다."""
import ipaddress
import socket

from host.robot_link import parse_telemetry
from host.roles import parse_role_status
from robot import config as settings


class RobotHub:
    def __init__(self, hosts, *, allow_real=False, receive_port=settings.TEL_PORT, command_port=settings.CMD_PORT,
                 socket_factory=socket.socket):
        if set(hosts) != {"A", "B"}:
            raise ValueError("both robot addresses required")
        self.peers = {}
        for robot, host in hosts.items():
            address = ipaddress.ip_address(host)
            if (address.version != 4 or address.is_unspecified or address.is_multicast
                    or str(address) == "255.255.255.255"
                    or (not address.is_loopback and not allow_real)):
                raise ValueError("real unicast robot address requires explicit authorization")
            self.peers[robot] = (str(address), command_port)
        if len(set(self.peers.values())) != 2:
            raise ValueError("robot addresses must be distinct")
        self.rejected = 0
        self.socket = socket_factory(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            self.socket.bind(("0.0.0.0", receive_port))
            self.socket.setblocking(False)
        except Exception:
            self.socket.close()
            raise

    def sender(self, robot):
        peer = self.peers[robot]

        def send(payload):
            if self.socket.sendto(payload, peer) != len(payload):
                raise OSError("incomplete UDP datagram")
        return send

    def receive(self):
        for _ in range(32):
            try:
                data, peer = self.socket.recvfrom(2048)
            except BlockingIOError:
                return
            try:
                tel = parse_role_status(data) if data.startswith(b"ROLE|") else parse_telemetry(data)
            except (ValueError, UnicodeError):
                self.rejected += 1
                continue
            if peer != self.peers[tel.robot]:
                self.rejected += 1
                continue
            yield tel.robot, data

    def close(self):
        self.socket.close()
