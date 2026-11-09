"""Optional explicit UDP transport; non-loopback requires caller opt-in."""
import ipaddress
import socket


class UdpTransport:
    def __init__(self, host="127.0.0.1", port=9100, receive_port=9101, *, allow_real=False):
        address = ipaddress.ip_address(host)
        if address.version != 4 or (not address.is_loopback and not allow_real):
            raise ValueError("non-loopback robot address requires explicit authorization")
        self.peer = (str(address), port)
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            self.socket.bind(("0.0.0.0", receive_port))
            self.socket.setblocking(False)
        except Exception:
            self.socket.close()
            raise

    def send(self, data):
        self.socket.sendto(data, self.peer)

    def receive(self):
        # Source IP and expected command port only; this is not authentication.
        for _ in range(16):
            try:
                data, peer = self.socket.recvfrom(2048)
            except BlockingIOError:
                break
            if peer == self.peer:
                yield data

    def close(self):
        self.socket.close()
