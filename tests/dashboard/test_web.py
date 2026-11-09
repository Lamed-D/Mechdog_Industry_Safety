import json
import threading
import time
import unittest
import urllib.error
import urllib.request

from dashboard.web.run import build_sim
from dashboard.web.server import DashboardServer
from dashboard.web.sim import start_loop


class WebTests(unittest.TestCase):
    def setUp(self):
        self.core, self.links = build_sim()
        self.lock = threading.Lock()
        self.server = DashboardServer(self.core, self.lock, "127.0.0.1", 0, token="t0k").start()
        self.addCleanup(self.server.stop)
        self.addCleanup(self.core.log.close)
        self.base = "http://127.0.0.1:%d" % self.server.address[1]

    def get(self, path):
        with urllib.request.urlopen(self.base + path, timeout=3) as r:
            return r.status, r.read()

    def post(self, path, body=None, token=None, raw=None):
        data = raw if raw is not None else json.dumps(body or {}).encode()
        req = urllib.request.Request(self.base + path, data=data, method="POST",
                                     headers={"Content-Type": "application/json"})
        if token:
            req.add_header("X-Dashboard-Token", token)
        try:
            with urllib.request.urlopen(req, timeout=3) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as error:
            with error:
                return error.code, json.loads(error.read())

    def tick(self, n=2):
        with self.lock:
            for _ in range(n):
                for link in self.links.values():
                    link.step()
                self.core.update()

    def test_index_and_state(self):
        status, body = self.get("/")
        self.assertEqual(status, 200)
        self.assertIn("전체 정지".encode(), body)
        status, body = self.get("/api/state")
        self.assertEqual(json.loads(body)["phase"], "standby")

    def test_estop_needs_no_token_and_survives_bad_body(self):
        status, result = self.post("/api/estop", raw=b"{not json")
        self.assertEqual(status, 200)
        self.assertTrue(result["ok"])
        for link in self.links.values():      # 링크 직접 + 시나리오 명령으로 두 번 걸려도 같은 정지
            self.assertTrue(link.sent)
            self.assertEqual(set(link.sent), {"ESTOP"})
            self.assertTrue(link.latched)
        self.assertEqual(json.loads(self.get("/api/state")[1])["phase"], "estop")

    def test_motion_operations_need_token(self):
        self.assertEqual(self.post("/api/operator", {"event": "start_patrol"})[0], 401)
        self.assertEqual(self.post("/api/operator", {"event": "start_patrol"}, token="wrong")[0], 401)
        self.assertEqual(self.post("/api/reset", {"robot": "A", "confirmed": True})[0], 401)
        status, result = self.post("/api/operator", {"event": "nope"}, token="t0k")
        self.assertEqual((status, result["reason"]), (400, "unknown_event"))

    def test_reset_requires_confirmation_then_robot_becomes_ready(self):
        self.tick()
        status, result = self.post("/api/reset", {"robot": "A", "confirmed": "yes"}, token="t0k")
        self.assertEqual(result["reason"], "confirmation_required")
        self.assertTrue(self.links["A"].latched)
        status, result = self.post("/api/reset", {"robot": "A", "confirmed": True}, token="t0k")
        self.assertTrue(result["ok"])
        self.tick()
        self.assertEqual(self.core.scenario.snapshot()["ready"], ["A"])
        status, result = self.post("/api/operator", {"event": "start_patrol"}, token="t0k")
        self.assertTrue(result["ok"])

    def test_loop_marks_link_lost_when_sim_robot_goes_offline(self):
        stop, thread = start_loop(self.core, self.links, self.lock, period_s=0.02)
        self.addCleanup(thread.join, 1)
        self.addCleanup(stop.set)
        time.sleep(0.1)
        self.links["B"].online = False
        time.sleep(0.6)
        with self.lock:
            state = self.core.snapshot()
        self.assertNotEqual(state["robots"]["B"]["link"], "ok")
        self.assertEqual(state["robots"]["A"]["link"], "ok")


if __name__ == "__main__":
    unittest.main()
