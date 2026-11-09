"""Pi 5 receiver for the custom vision-camera firmware (firmware/vision_cam).

Endpoints: :80/status (JSON), :80/capture (JPEG), :81/stream (MJPEG, latest frame only).
Frames are kept in memory only and never written to disk. Network is touched only when a
method is called; importing this module opens nothing.
"""
from dataclasses import dataclass
import json
import math
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

ROBOTS = ("A", "B")
MAX_FRAME_BYTES = 512 * 1024      # VGA JPEG is ~20-40 KB; anything this big is a broken stream
MAX_HEADER_LINES = 16


@dataclass(frozen=True)
class CameraEndpoint:
    robot: str
    host: str
    http_port: int = 80
    stream_port: int = 81
    key: str | None = None

    def __post_init__(self):
        if self.robot not in ROBOTS:
            raise ValueError("unknown robot")
        if not self.host or any(c in self.host for c in "/?#@ "):
            raise ValueError("invalid camera host")
        for port in (self.http_port, self.stream_port):
            if not 0 < port < 65536:
                raise ValueError("invalid port")

    @staticmethod
    def default_host(robot):
        """mDNS name the firmware registers, e.g. mechdog-a-cam.local."""
        return "mechdog-%s-cam.local" % robot.lower()

    def url(self, path):
        port = self.stream_port if path == "/stream" else self.http_port
        query = "?" + urllib.parse.urlencode({"key": self.key}) if self.key else ""
        return "http://%s:%d%s%s" % (self.host, port, path, query)


@dataclass(frozen=True)
class Frame:
    robot: str
    jpeg: bytes
    seq: int | None
    camera_age_ms: int | None   # age reported by the camera when the frame was sent
    captured_at: float          # estimated capture time on the receiver clock (monotonic seconds):
                                # part-header arrival minus camera_age_ms, so slow transfer counts as age


def is_jpeg(data):
    return len(data) > 4 and data[:2] == b"\xff\xd8" and data[-2:] == b"\xff\xd9"


def _optional_int(value):
    if value is None:
        return None
    value = value.strip()
    return int(value) if value.isascii() and value.isdigit() else None


def _captured_at(header_time, camera_age_ms):
    return header_time - (camera_age_ms or 0) / 1000.0


def parse_status(obj, robot):
    """Validate /status JSON. Raises ValueError on anything missing or inconsistent."""
    try:
        camera, wifi, stream = obj["camera"], obj["wifi"], obj["stream"]
        result = {
            "robot": obj["robot"],
            "fw": str(obj["fw"]),
            "camera_ok": camera["ok"],
            "sensor": str(camera["sensor"]),
            "width": camera["width"],
            "height": camera["height"],
            "fps": camera["fps"],
            "idle": camera["idle"],
            "frame_age_ms": camera["frame_age_ms"],
            "wifi_mode": wifi["mode"],
            "rssi": wifi["rssi"],
            "stream_clients": stream["clients"],
            "max_stream_clients": stream["max_clients"],
            "recognition": obj["recognition"],
        }
    except (KeyError, TypeError) as error:
        raise ValueError("incomplete camera status") from error
    if result["robot"] != robot:
        raise ValueError("camera reports another robot")
    for name in ("camera_ok", "idle", "recognition"):
        if not isinstance(result[name], bool):
            raise ValueError("invalid %s" % name)
    for name in ("width", "height", "frame_age_ms", "rssi", "stream_clients", "max_stream_clients"):
        if not isinstance(result[name], int) or isinstance(result[name], bool):
            raise ValueError("invalid %s" % name)
    if not isinstance(result["fps"], (int, float)) or not math.isfinite(result["fps"]) or result["fps"] < 0:
        raise ValueError("invalid fps")
    if result["wifi_mode"] not in ("sta", "ap", "sta+ap", "none"):
        raise ValueError("invalid wifi mode")
    return result


class CameraClient:
    """One-shot requests (status, capture). Failures are reported, never treated as 'no person'."""

    # timeout is longer than the camera's own /capture wait (1.5 s) so its "503 no frame" arrives.
    def __init__(self, endpoint, timeout_s=5.0, max_frame_age_ms=1000, opener=None, clock=time.monotonic):
        self.endpoint = endpoint
        self.timeout_s = timeout_s
        self.max_frame_age_ms = max_frame_age_ms
        self._open = opener or urllib.request.urlopen
        self._clock = clock

    def status(self):
        try:
            with self._open(self.endpoint.url("/status"), timeout=self.timeout_s) as response:
                body = response.read(8192)
            status = parse_status(json.loads(body), self.endpoint.robot)
        except urllib.error.HTTPError as error:
            error.close()
            return {"robot": self.endpoint.robot, "status": "unknown", "reason": "http_%d" % error.code}
        except (OSError, ValueError) as error:
            return {"robot": self.endpoint.robot, "status": "unknown", "reason": type(error).__name__}
        # Reachable is not healthy: a lost camera or stale frames are reported as unknown.
        if not status["camera_ok"]:
            return {**status, "status": "unknown", "reason": "camera_not_ok"}
        if not status["idle"] and not 0 <= status["frame_age_ms"] <= self.max_frame_age_ms:
            return {**status, "status": "unknown", "reason": "stale_frames"}
        return {**status, "status": "ok"}

    def capture(self):
        """Returns a Frame or None. A camera error is 'unknown', not an empty scene."""
        try:
            with self._open(self.endpoint.url("/capture"), timeout=self.timeout_s) as response:
                header_time = self._clock()
                if response.headers.get("X-Robot") != self.endpoint.robot:
                    return None
                data = response.read(MAX_FRAME_BYTES + 1)
                headers = response.headers
            if len(data) > MAX_FRAME_BYTES or not is_jpeg(data):
                return None
            age = _optional_int(headers.get("X-Frame-Age-Ms"))
            seq = _optional_int(headers.get("X-Frame-Seq"))
            if seq is None:
                return None
            if age is None or not 0 <= self._clock() - _captured_at(header_time, age) <= self.max_frame_age_ms / 1000:
                return None
            return Frame(self.endpoint.robot, data, seq, age,
                         _captured_at(header_time, age))
        except urllib.error.HTTPError as error:
            error.close()
            return None
        except (OSError, ValueError):
            return None


def read_mjpeg(stream, robot, clock=time.monotonic):
    """Yield Frames from a multipart MJPEG byte stream (file-like with readline/read).

    Uses Content-Length per part. Raises ValueError on a malformed stream so the caller
    reconnects instead of guessing at frame boundaries.
    """
    while True:
        line = stream.readline(256)
        if not line:
            return
        if not line.strip():
            continue                      # CRLF before the boundary
        if not line.startswith(b"--"):
            raise ValueError("missing multipart boundary")
        headers = {}
        for _ in range(MAX_HEADER_LINES):
            header = stream.readline(256)
            if not header:
                return
            if not header.strip():
                break
            name, _, value = header.decode("latin-1").partition(":")
            headers[name.strip().lower()] = value.strip()
        else:
            raise ValueError("too many part headers")
        header_time = clock()          # body transfer time below counts toward the frame's age
        length = _optional_int(headers.get("content-length"))
        if length is None or length > MAX_FRAME_BYTES:
            raise ValueError("invalid content length")
        data = stream.read(length)
        if len(data) < length:
            return
        if not is_jpeg(data):
            raise ValueError("part is not a JPEG")
        age = _optional_int(headers.get("x-frame-age-ms"))
        yield Frame(robot, data, _optional_int(headers.get("x-frame-seq")), age, _captured_at(header_time, age))


class LatestFrameReceiver:
    """Background MJPEG reader that keeps only the newest frame per camera.

    latest() returns None when the newest frame's estimated capture time (header arrival minus the
    camera-reported age, so transfer delay counts) is older than max_age_s, when the camera reported
    it as older than max_camera_age_ms, or when the age header is missing. Callers must treat None as
    'unknown', never as 'nothing detected'.
    """

    def __init__(self, endpoint, max_age_s=1.0, max_camera_age_ms=500, timeout_s=5.0,
                 retry_s=2.0, opener=None, clock=time.monotonic):
        if not (max_age_s > 0 and max_camera_age_ms > 0 and timeout_s > 0 and retry_s > 0):
            raise ValueError("invalid receiver limits")
        self.endpoint = endpoint
        self.max_age_s = max_age_s
        self.max_camera_age_ms = max_camera_age_ms
        self.timeout_s = timeout_s
        self.retry_s = retry_s
        self._open = opener or urllib.request.urlopen
        self._clock = clock
        self._lock = threading.Lock()
        self._frame = None
        self._stop = threading.Event()
        self._thread = None
        self.frames = 0
        self.bytes_received = 0
        self.errors = 0
        self.last_error = None

    def start(self):
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, name="cam-%s" % self.endpoint.robot, daemon=True)
            self._thread.start()
        return self

    def stop(self, join_s=2.0):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(join_s)

    def latest(self):
        with self._lock:
            frame = self._frame
        # Without the camera's age header the frame's real age is unknown: not fresh.
        if frame is None or frame.seq is None or frame.camera_age_ms is None or frame.camera_age_ms > self.max_camera_age_ms:
            return None
        if not 0 <= self._clock() - frame.captured_at <= self.max_age_s:
            return None
        return frame

    def state(self):
        if self.latest() is not None:
            return {"robot": self.endpoint.robot, "status": "streaming", "frames": self.frames}
        return {"robot": self.endpoint.robot, "status": "unknown",
                "reason": self.last_error or "no_fresh_frame", "frames": self.frames}

    def feed(self, stream):
        """Read one connection until it ends. Separated from the thread for tests."""
        previous = None
        for frame in read_mjpeg(stream, self.endpoint.robot, self._clock):
            if frame.seq is not None and previous is not None and frame.seq <= previous:
                with self._lock:
                    self._frame = None
                raise ValueError("frame sequence did not advance")
            previous = frame.seq
            with self._lock:
                self._frame = frame
            self.frames += 1
            self.bytes_received += len(frame.jpeg)
            self.last_error = None
            if self._stop.is_set():
                return

    def _run(self):
        while not self._stop.is_set():
            try:
                with self._open(self.endpoint.url("/stream"), timeout=self.timeout_s) as response:
                    if response.headers.get("X-Robot") != self.endpoint.robot:
                        raise ValueError("camera reports another robot")
                    self.feed(response)
                self.last_error = "stream_ended"
            except urllib.error.HTTPError as error:
                error.close()
                self.last_error = "http_%d" % error.code
            except (OSError, ValueError) as error:
                self.last_error = type(error).__name__
            with self._lock:
                self._frame = None
            self.errors += 1
            self._stop.wait(self.retry_s)
