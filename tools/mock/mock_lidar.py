"""Local RPLIDAR emulator. Run: python -m tools.mock.mock_lidar.

Synthetic square room only. Never connects to a robot.
"""

import argparse
import math
import random
import socket
import socketserver
import threading
import time


# A1M8-R6 standard-scan profile, not the device's 8 kHz measurement mode.
MIN_DISTANCE_MM = 150
MAX_DISTANCE_MM = 12000
POINTS_PER_ROTATION = 360
ROTATION_HZ = 5.5
SAMPLES_PER_SECOND = POINTS_PER_ROTATION * ROTATION_HZ
BATCH_SAMPLES = 20


def descriptor(size, mode, kind):
    return b"\xa5\x5a" + (size | mode << 30).to_bytes(4, "little") + bytes([kind])


def room_sample(index, points=POINTS_PER_ROTATION, noise_mm=0, rng=None):
    if points < 1 or not math.isfinite(noise_mm) or noise_mm < 0:
        raise ValueError("invalid synthetic scan parameters")
    angle = index % points * 360 / points
    radians = math.radians(angle)
    distance = 2000 / max(abs(math.cos(radians)), abs(math.sin(radians)))
    distance += (rng or random).uniform(-noise_mm, noise_mm)
    distance = max(MIN_DISTANCE_MM, min(MAX_DISTANCE_MM, distance))
    return (bytes([(40 << 2) | (1 if index % points == 0 else 2)])
            + ((round(angle * 64) << 1) | 1).to_bytes(2, "little")
            + round(distance * 4).to_bytes(2, "little"))


class _Handler(socketserver.BaseRequestHandler):
    def handle(self):
        server = self.server
        self.request.settimeout(0.01)
        pending = bytearray()
        scanning = False
        count = 0
        rng = random.Random(0)
        next_batch = time.monotonic()
        try:
            while not server.stopping.is_set():
                if scanning:
                    self.request.settimeout(max(0.0001, min(0.01, next_batch - time.monotonic())))
                try:
                    data = self.request.recv(1024)
                    if not data:
                        return
                    pending.extend(data)
                except socket.timeout:
                    pass
                while len(pending) >= 2:
                    if pending[0] != 0xA5:
                        del pending[0]
                        continue
                    command = pending[1]
                    del pending[:2]
                    server.commands.append(command)
                    if command in (0x25, 0x40):
                        scanning = False
                    elif command == 0x52:
                        self.request.sendall(descriptor(3, 0, 6) + bytes([server.health, 0, 0]))
                    elif command == 0x50:
                        self.request.sendall(descriptor(20, 0, 4) + bytes(20))
                    elif command == 0x20:
                        self.request.sendall(descriptor(5, 1, 0x81))
                        scanning = True
                        next_batch = time.monotonic()
                if scanning and time.monotonic() >= next_batch:
                    batch = bytearray()
                    for _ in range(BATCH_SAMPLES):
                        packet = room_sample(count, noise_mm=server.noise_mm, rng=rng)
                        count += 1
                        if server.corrupt_every and count % server.corrupt_every == 0:
                            packet = b"\x00" * 5
                        batch.extend(packet)
                    self.request.sendall(batch)
                    # Never burst to catch up after a delayed send or busy input.
                    next_batch = time.monotonic() + BATCH_SAMPLES / SAMPLES_PER_SECOND
                    if server.disconnect_after and count >= server.disconnect_after:
                        return
        except OSError:
            return


class MockLidar(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True
    block_on_close = True

    def __init__(self, address=("127.0.0.1", 20108), *, noise_mm=0,
                 corrupt_every=0, disconnect_after=0, health=0):
        if not math.isfinite(noise_mm) or noise_mm < 0 or corrupt_every < 0 or disconnect_after < 0:
            raise ValueError("fault parameters must be nonnegative")
        self.noise_mm = noise_mm
        self.corrupt_every = corrupt_every
        self.disconnect_after = disconnect_after
        self.health = health
        self.commands = []
        self.stopping = threading.Event()
        super().__init__(address, _Handler)

    def server_close(self):
        self.stopping.set()
        super().server_close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=20108)
    parser.add_argument("--noise-mm", type=float, default=0)
    parser.add_argument("--corrupt-every", type=int, default=0)
    parser.add_argument("--disconnect-after", type=int, default=0)
    args = parser.parse_args()
    with MockLidar(port_address := ("127.0.0.1", args.port),
                   noise_mm=args.noise_mm, corrupt_every=args.corrupt_every,
                   disconnect_after=args.disconnect_after) as server:
        print("Mock lidar listening on", port_address)
        try:
            server.serve_forever(poll_interval=0.1)
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
