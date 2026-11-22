"""Request one bounded JPEG at a time from the camera's USB UART."""

import threading
import time

from host.vision.camera_client import is_jpeg

MAX_JPEG = 128 * 1024
HEADER = b"MECHDOG_JPEG "
TIMEOUT_S = 16


def read_frame(port, stop, *, clock=time.monotonic):
    port.write(b"frame\n")
    deadline = clock() + TIMEOUT_S
    while clock() < deadline and not stop.is_set():
        line = port.read_until(b"\n", size=96)
        if line.startswith(HEADER):
            if not line.endswith(b"\n") or not line[len(HEADER):].strip().isdigit():
                raise ValueError("invalid USB JPEG header")
            length = int(line[len(HEADER):])
            if not 0 < length <= MAX_JPEG:
                raise ValueError("camera has no JPEG or JPEG exceeds USB limit")
            break
    else:
        raise TimeoutError("USB camera did not return a JPEG header")
    frame = bytearray()
    while len(frame) < length and clock() < deadline and not stop.is_set():
        frame.extend(port.read(min(4096, length - len(frame))))
    if len(frame) != length:
        raise TimeoutError("USB camera JPEG was truncated")
    if not is_jpeg(frame):
        raise ValueError("invalid USB JPEG")
    return bytes(frame)


class UsbCamera:
    def __init__(self, device):
        self.device = device
        self.stop_event = threading.Event()
        self.lock = threading.Lock()
        self.latest = None
        self.stamp = 0
        self.error = None

    def run(self):
        try:
            import serial

            port = serial.Serial(baudrate=115200, timeout=0.2, write_timeout=1)
            port.port = self.device
            port.dtr = port.rts = False
            with port:
                while not self.stop_event.is_set():
                    try:
                        frame = read_frame(port, self.stop_event)
                    except (ValueError, TimeoutError) as error:
                        with self.lock:
                            self.latest, self.error = None, str(error)
                        self.stop_event.wait(0.5)
                    else:
                        with self.lock:
                            self.latest, self.stamp, self.error = frame, time.monotonic(), None
        except (OSError, ImportError) as error:
            with self.lock:
                self.latest, self.error = None, str(error)

    def snapshot(self):
        with self.lock:
            if self.latest and time.monotonic() - self.stamp < TIMEOUT_S:
                return self.latest, None
            return None, self.error or "USB 카메라 프레임 대기"
