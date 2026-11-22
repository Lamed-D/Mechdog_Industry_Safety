"""Wi-Fi MJPEG reception and CPU person detection."""

from collections import deque
from threading import Event, Lock, Thread
from time import monotonic
from urllib.request import urlopen


class CameraMonitor:
    def __init__(self, url, cv):
        self.url = url
        self.cv = cv
        self.detector = cv.HOGDescriptor()
        self.detector.setSVMDetector(cv.HOGDescriptor_getDefaultPeopleDetector())
        self.lock = Lock()
        self.stop_event = Event()
        self.times = deque()
        self.jpeg = None
        self.sequence = 0
        self.result = None

    def start(self):
        Thread(target=self.receive, daemon=True).start()
        Thread(target=self.detect, daemon=True).start()

    def receive(self):
        while not self.stop_event.is_set():
            try:
                with urlopen(self.url, timeout=2) as stream:
                    boundary = stream.headers.get_param("boundary", "").encode("ascii")
                    if not boundary:
                        raise ValueError("missing MJPEG boundary")
                    while not self.stop_event.is_set():
                        line = stream.readline(1024)
                        if not line:
                            break
                        if line.strip() != b"--" + boundary:
                            continue
                        headers = {}
                        for _ in range(16):
                            line = stream.readline(1024).strip()
                            if not line:
                                break
                            key, value = line.split(b":", 1)
                            headers[key.lower()] = value.strip()
                        size = int(headers[b"content-length"])
                        if not 0 < size <= 2_000_000:
                            raise ValueError("invalid JPEG size")
                        jpeg = stream.read(size)
                        if len(jpeg) != size:
                            break
                        if not (jpeg.startswith(b"\xff\xd8") and jpeg.endswith(b"\xff\xd9")):
                            continue
                        with self.lock:
                            now = monotonic()
                            self.times.append(now)
                            while self.times[0] < now - 2:
                                self.times.popleft()
                            self.sequence += 1
                            self.jpeg = jpeg
            except (OSError, ValueError, KeyError):
                pass
            self.stop_event.wait(1)

    def detect(self):
        import numpy as np

        previous = 0
        streak = 0
        previous_time = float("-inf")
        while not self.stop_event.wait(0.03):
            with self.lock:
                seq, jpeg = self.sequence, self.jpeg
                received = self.times[-1] if self.times else 0
            if seq == previous or monotonic() - received > 1:
                continue
            previous = seq
            try:
                image = self.cv.imdecode(np.frombuffer(jpeg, np.uint8), self.cv.IMREAD_COLOR)
                if image is None:
                    raise ValueError("invalid JPEG")
                height, width = image.shape[:2]
                if width < 64 or height < 128:
                    raise ValueError("frame too small for people detector")
                if width > 640:
                    image = self.cv.resize(image, (640, max(1, round(height * 640 / width))))
                boxes, _ = self.detector.detectMultiScale(image, winStride=(8, 8))
            except (ValueError, self.cv.error):
                streak = 0
                with self.lock:
                    self.result = None
                continue
            if received - previous_time > 1:
                streak = 0
            previous_time = received
            streak = streak + 1 if len(boxes) else 0
            with self.lock:
                self.result = (received, None if streak == 1 else streak >= 2)

    def snapshot(self):
        with self.lock:
            now = monotonic()
            age = now - self.times[-1] if self.times else None
            fps = sum(t >= now - 2 for t in self.times) / 2
            person = self.result[1] if self.result and now - self.result[0] <= 1 else None
            return {
                "fps": fps,
                "frame_age": age,
                "person": person,
            }, self.jpeg if age is not None and age <= 1 else None
