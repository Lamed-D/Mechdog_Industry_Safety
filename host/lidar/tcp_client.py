"""Explicit TCP scan sessions with bounded startup and idle timeouts."""

import socket
import threading
import time

from .rplidar_protocol import Command, SampleParser, parse_descriptor, request


class LidarHealthError(ValueError):
    """Device error requires operator recovery; never reset automatically."""


class LidarClient:
    def __init__(self, host, port=20108, timeout=2, retry_delay=0.5, on_health=None):
        if timeout <= 0 or retry_delay < 0:
            raise ValueError("invalid timing")
        self.address = (host, port)
        self.timeout = timeout
        self.retry_delay = retry_delay
        self.on_health = on_health

    def _exact(self, sock, size, stop):
        data = bytearray()
        deadline = time.monotonic() + self.timeout
        while len(data) < size:
            if stop.is_set():
                raise InterruptedError("session cancelled")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("response timeout")
            sock.settimeout(min(remaining, 0.1))
            try:
                chunk = sock.recv(size - len(data))
            except socket.timeout:
                continue
            if not chunk:
                raise ConnectionError("lidar disconnected")
            data.extend(chunk)
        return bytes(data)

    def _descriptor(self, sock, expected, stop):
        # Bound both byte count and time while discarding stale stream bytes.
        window = bytearray()
        deadline = time.monotonic() + self.timeout
        for _ in range(65536):
            if time.monotonic() >= deadline:
                raise TimeoutError("descriptor timeout")
            window.extend(self._exact(sock, 1, stop))
            if len(window) > 7:
                del window[0]
            if len(window) == 7:
                try:
                    descriptor = parse_descriptor(window)
                except ValueError:
                    continue
                if (descriptor.size, descriptor.mode, descriptor.data_type) == expected:
                    return descriptor
        raise ValueError("descriptor not found")

    def session(self, stop=None):
        """Yield samples for one connection; failure is reported to the caller."""
        stop = stop if stop is not None else threading.Event()
        with socket.create_connection(self.address, self.timeout) as sock:
            try:
                sock.sendall(request(Command.STOP))
                if stop.wait(0.1):
                    return
                sock.sendall(request(Command.GET_HEALTH))
                self._descriptor(sock, (3, 0, 6), stop)
                health = self._exact(sock, 3, stop)
                code = int.from_bytes(health[1:3], "little")
                if self.on_health:
                    self.on_health(health[0], code)
                if health[0] not in (0, 1):
                    raise LidarHealthError("lidar health error: status=%d code=%d" % (health[0], code))
                sock.sendall(request(Command.SCAN))
                self._descriptor(sock, (5, 1, 0x81), stop)
                parser = SampleParser()
                last_sample = time.monotonic()
                sock.settimeout(min(self.timeout, 0.1))
                while not stop.is_set():
                    if time.monotonic() - last_sample >= self.timeout:
                        raise TimeoutError("no valid lidar samples")
                    try:
                        data = sock.recv(4096)
                    except socket.timeout:
                        continue
                    if not data:
                        raise ConnectionError("lidar disconnected")
                    samples = parser.feed(data)
                    if samples:
                        last_sample = time.monotonic()
                    yield from samples
            finally:
                try:
                    sock.sendall(request(Command.STOP))
                except OSError:
                    pass

    def run(self, on_sample, on_disconnect, stop):
        """Reconnect until stopped; caller must discard partial scans on failure."""
        while not stop.is_set():
            try:
                for sample in self.session(stop):
                    on_sample(sample)
            except (OSError, ValueError) as error:
                on_disconnect(error)
                if isinstance(error, LidarHealthError):
                    return
            if stop.wait(self.retry_delay):
                break
