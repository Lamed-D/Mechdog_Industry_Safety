"""느린 디스크/백엔드 기록을 제어 잠금 밖에서 처리하는 제한 큐."""
import json
import queue
import threading
import time

from .log import _clean


class BufferedEventLog:
    def __init__(self, backend, capacity=512, max_event_bytes=16384, wall=time.time):
        if isinstance(capacity, bool) or not isinstance(capacity, int) or capacity <= 0 or max_event_bytes <= 0:
            raise ValueError("positive log limits required")
        self.backend = backend
        self.wall = wall
        self.max_bytes = max_event_bytes
        self._queue = queue.Queue(capacity)
        self._state = threading.Condition()
        self._closed = False
        self._pending = self._failures = 0
        self._thread = threading.Thread(target=self._run, name="event-log", daemon=True)
        self._thread.start()

    @property
    def failures(self):
        with self._state:
            return self._failures

    def record(self, kind, robot=None, detail=None):
        try:
            event_wall = self.wall()
            payload = json.dumps(_clean(detail or {}), ensure_ascii=False, allow_nan=False)
            if len(payload.encode("utf-8")) > self.max_bytes or len(str(kind)) > 64:
                raise ValueError("event too large")
        except Exception:
            with self._state:
                self._failures += 1
            return False
        with self._state:
            if self._closed:
                self._failures += 1
                return False
            try:
                self._queue.put_nowait((str(kind), robot, payload, event_wall))
            except queue.Full:
                self._failures += 1
                return False
            self._pending += 1
            return True  # 큐에 넣었다는 뜻이며 디스크 저장 완료 ACK가 아님

    def _run(self):
        try:
            while True:
                try:
                    kind, robot, payload, event_wall = self._queue.get(timeout=.05)
                except queue.Empty:
                    with self._state:
                        if self._closed and self._pending == 0:
                            return
                    continue
                try:
                    if not self.backend.record(kind, robot, json.loads(payload), event_wall=event_wall):
                        with self._state:
                            self._failures += 1
                except Exception:
                    with self._state:
                        self._failures += 1
                finally:
                    with self._state:
                        self._pending -= 1
                        self._state.notify_all()
        finally:
            try:
                self.backend.close()
            except Exception:
                with self._state:
                    self._failures += 1

    def flush(self, timeout_s=1):
        deadline = time.monotonic() + timeout_s
        with self._state:
            while self._pending:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self._state.wait(remaining)
            return True

    def recent(self, limit=50):
        # 조회는 UI/관리 경로 전용. 제어 루프에서 호출하지 않습니다.
        return self.backend.recent(limit)

    def close(self, join_s=1):
        with self._state:
            self._closed = True
        self._thread.join(join_s)
        return not self._thread.is_alive()
