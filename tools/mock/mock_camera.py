"""Fake vision-camera server with the same endpoints as firmware/vision_cam.

Run: python -m tools.mock.mock_camera --robot A --port 8080 --stream-port 8081
Serves synthetic JPEG-shaped bytes only (no real images, no people). Never touches a robot.
"""
import argparse
import http.server
import json
import threading
import time
import urllib.parse

BOUNDARY = "mechdogframe"


def synthetic_jpeg(seq):
    """Bytes framed like a JPEG (SOI ... EOI). Not decodable as a real picture."""
    return b"\xff\xd8" + b"MOCK%08d" % seq + b"\x00" * 64 + b"\xff\xd9"


class CameraState:
    def __init__(self, robot="A", key=None, fps=20.0):
        self.robot = robot
        self.key = key
        self.fps = fps
        self.seq = 0
        self.stall = threading.Event()   # set → stream stops sending without closing
        self.clients = 0
        self.lock = threading.Lock()

    def next_frame(self):
        with self.lock:
            self.seq += 1
            return self.seq, synthetic_jpeg(self.seq)

    def status(self):
        return {"robot": self.robot, "host": "mechdog-%s-cam" % self.robot.lower(), "fw": "mock",
                "uptime_s": 1,
                "wifi": {"mode": "sta", "ip": "127.0.0.1", "rssi": -50, "reconnects": 0},
                "camera": {"ok": True, "sensor": "MOCK", "psram": True, "width": 640, "height": 480,
                           "quality": 12, "fps": self.fps, "idle": False, "frames": self.seq,
                           "failures": 0, "reinits": 0, "frame_age_ms": 10, "frame_bytes": 78},
                "stream": {"port": 81, "clients": self.clients, "max_clients": 2},
                "memory": {"heap_free": 100000, "psram_free": 4000000},
                "i2c": {"addr": 0x53, "requests": 0}, "recognition": False, "auth": bool(self.key)}


def make_handler(state):
    class Handler(http.server.BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.0"

        def log_message(self, *args):
            pass

        def _authorized(self):
            if not state.key:
                return True
            query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            return query.get("key") == [state.key]

        def _send(self, code, body, content_type="text/plain", headers=()):
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            for name, value in headers:
                self.send_header(name, value)
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = urllib.parse.urlparse(self.path).path
            if not self._authorized():
                return self._send(401, b"key required\n")
            if path == "/status":
                return self._send(200, json.dumps(state.status()).encode(), "application/json")
            if path == "/capture":
                seq, jpeg = state.next_frame()
                return self._send(200, jpeg, "image/jpeg",
                                  (("X-Robot", state.robot), ("X-Frame-Seq", str(seq)), ("X-Frame-Age-Ms", "5")))
            if path == "/stream":
                return self._stream()
            return self._send(404, b"not found\n")

        def _stream(self):
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace;boundary=" + BOUNDARY)
            self.send_header("X-Robot", state.robot)
            self.end_headers()
            state.clients += 1
            try:
                while True:
                    if state.stall.is_set():
                        time.sleep(0.02)
                        continue
                    seq, jpeg = state.next_frame()
                    head = ("\r\n--%s\r\nContent-Type: image/jpeg\r\nContent-Length: %d\r\n"
                            "X-Frame-Seq: %d\r\nX-Frame-Age-Ms: 5\r\n\r\n" % (BOUNDARY, len(jpeg), seq))
                    self.wfile.write(head.encode() + jpeg)
                    self.wfile.flush()
                    time.sleep(1.0 / state.fps)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass
            finally:
                state.clients -= 1

    return Handler


def serve(state, host="127.0.0.1", port=0):
    server = http.server.ThreadingHTTPServer((host, port), make_handler(state))
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--robot", default="A", choices=("A", "B"))
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--stream-port", type=int, default=8081)
    parser.add_argument("--key")
    args = parser.parse_args()
    state = CameraState(args.robot, args.key)
    serve(state, "127.0.0.1", args.port)
    serve(state, "127.0.0.1", args.stream_port)
    print("mock camera %s: http://127.0.0.1:%d/status  stream :%d/stream" % (args.robot, args.port, args.stream_port))
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
