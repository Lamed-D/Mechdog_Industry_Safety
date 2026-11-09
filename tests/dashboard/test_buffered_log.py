import threading
import unittest

from dashboard.core import BufferedEventLog, DashboardCore, EventLog
from dashboard.web.sim import SimLink
from scenario import Scenario


class SlowBackend:
    def __init__(self):
        self.entered, self.release = threading.Event(), threading.Event()
        self.rows = []
        self.times = []
        self.closed = False

    def record(self, kind, robot, detail, *, event_wall=None):
        self.entered.set()
        if not self.release.wait(5):
            raise TimeoutError("injected slow disk")
        self.rows.append((kind, robot, detail))
        self.times.append(event_wall)
        return True

    def close(self):
        self.closed = True


class BufferedLogTests(unittest.TestCase):
    def test_sqlite_keeps_event_time_instead_of_delayed_write_time(self):
        backend = EventLog(wall=lambda: 999)
        log = BufferedEventLog(backend, wall=lambda: 42)
        try:
            self.assertTrue(log.record("test", "A", {"source": "synthetic"}))
            self.assertTrue(log.flush(1))
            self.assertEqual(backend.recent(1)[0]["wall"], 42)
        finally:
            log.close()

    def setUp(self):
        self.backend = SlowBackend()
        self.log = BufferedEventLog(self.backend, capacity=1)
        self.addCleanup(self.log.close)
        self.addCleanup(self.backend.release.set)
        self.assertTrue(self.log.record("blocked"))
        self.assertTrue(self.backend.entered.wait(1))

    def test_blocked_disk_cannot_delay_both_estop_requests(self):
        links = {r: SimLink(r) for r in ("A", "B")}
        core = DashboardCore(Scenario(), links, self.log)
        done = threading.Event()

        def stop():
            core.estop_all()
            done.set()

        thread = threading.Thread(target=stop, daemon=True)
        thread.start()
        self.assertTrue(done.wait(1), "ESTOP waited for blocked disk")
        self.assertTrue(all(link.sent and link.latched for link in links.values()))
        self.assertFalse(self.backend.release.is_set())
        self.assertFalse(self.log.flush(.01))

    def test_queue_is_bounded_and_freezes_clean_metadata(self):
        detail = {"value": [1], "jpeg": b"synthetic"}
        self.log.wall = lambda: 42
        self.assertTrue(self.log.record("queued", "A", detail))
        detail["value"][0] = 999
        self.log.wall = lambda: 100
        self.assertFalse(self.log.record("overflow"))
        self.assertEqual(self.log.failures, 1)
        self.backend.release.set()
        self.assertTrue(self.log.flush(1))
        self.assertEqual(self.backend.rows[1][2], {"value": [1], "jpeg": "<bytes omitted>"})
        self.assertEqual(self.backend.times[1], 42)

    def test_oversized_or_invalid_metadata_is_dropped_without_waiting(self):
        for detail in ({"x": "x" * 20000}, {"x": float("nan")}):
            self.assertFalse(self.log.record("invalid", detail=detail))
        self.assertEqual(self.log.failures, 2)
