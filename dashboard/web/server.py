"""대시보드 웹 서버 (WP-D3). 표준 라이브러리만 사용(http.server + JSON 폴링).

GET  /             화면(static/index.html)
GET  /api/state    DashboardCore.snapshot() JSON
POST /api/estop    전체 정지 — 확인 없이 바로
POST /api/operator {"event": "operator_ack" | "start_guide" | ...}
POST /api/reset    {"robot": "A", "confirmed": true} — 화면의 확인 창을 거친 요청만

- 기본 주소는 127.0.0.1. 다른 기기에서 열려면 host 를 명시합니다(전용 공유기 안에서만).
- token 을 주면 POST 요청에 X-Dashboard-Token 머리글이 맞아야 합니다. 단, **전체 정지는 토큰 없이도** 받습니다
  (멈추는 쪽은 막지 않음). 이동을 일으킬 수 있는 조작과 래치 해제만 토큰으로 보호합니다.
- 모든 core 호출은 하나의 잠금으로 직렬화합니다(10Hz 갱신 루프와 동시에 쓰기 때문).
"""
import hmac
import http.server
import json
import pathlib
import threading

STATIC = pathlib.Path(__file__).resolve().parent / "static"
MAX_BODY = 1024


class DashboardServer:
    def __init__(self, core, lock=None, host="127.0.0.1", port=8000, token=None):
        self.core = core
        self.lock = lock or threading.Lock()
        self.token = token
        self.httpd = http.server.ThreadingHTTPServer((host, port), self._handler())
        self.httpd.daemon_threads = True
        self.thread = None

    @property
    def address(self):
        return self.httpd.server_address

    def start(self):
        self.thread = threading.Thread(target=self.httpd.serve_forever, name="dashboard-http", daemon=True)
        self.thread.start()
        return self

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()

    # ---- 요청 처리 ---------------------------------------------------------
    def handle_post(self, path, body, token):
        if path == "/api/estop":
            with self.lock:
                return 200, self.core.estop_all(source="dashboard")
        if self.token and not (token and hmac.compare_digest(token, self.token)):
            return 401, {"ok": False, "reason": "token_required"}
        if path == "/api/operator":
            event = body.get("event")
            with self.lock:
                try:
                    return 200, self.core.operator(event)
                except ValueError:
                    return 400, {"ok": False, "reason": "unknown_event"}
        if path == "/api/reset":
            robot, confirmed = body.get("robot"), body.get("confirmed") is True
            with self.lock:
                try:
                    return 200, self.core.reset_latch(robot, confirmed=confirmed)
                except ValueError:
                    return 400, {"ok": False, "reason": "unknown_robot"}
        return 404, {"ok": False, "reason": "not_found"}

    def _handler(self):
        server = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _send(self, code, payload, content_type="application/json; charset=utf-8"):
                data = payload if isinstance(payload, bytes) else json.dumps(payload, ensure_ascii=False).encode()
                self.send_response(code)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                if self.path in ("/", "/index.html"):
                    return self._send(200, (STATIC / "index.html").read_bytes(), "text/html; charset=utf-8")
                if self.path == "/api/state":
                    with server.lock:
                        snapshot = server.core.snapshot()
                    return self._send(200, snapshot)
                return self._send(404, {"ok": False, "reason": "not_found"})

            def do_POST(self):
                try:
                    length = int(self.headers.get("Content-Length") or 0)
                except ValueError:
                    length = -1
                if not 0 <= length <= MAX_BODY:
                    return self._send(400, {"ok": False, "reason": "bad_length"})
                raw = self.rfile.read(length) if length else b"{}"
                try:
                    body = json.loads(raw or b"{}")
                    if not isinstance(body, dict):
                        raise ValueError
                except ValueError:
                    # 전체 정지는 본문이 깨져도 받습니다.
                    if self.path != "/api/estop":
                        return self._send(400, {"ok": False, "reason": "bad_json"})
                    body = {}
                code, payload = server.handle_post(self.path, body, self.headers.get("X-Dashboard-Token"))
                return self._send(code, payload)

        return Handler
