"""대시보드 사건 기록 (SQLite, 표준 라이브러리만).

영상·사진 바이트는 저장하지 않습니다. 사진이 필요하면 저장소 밖 로컬 경로 문자열만 남깁니다.
기록 실패는 정지 같은 안전 조작을 막지 않도록 예외 대신 실패 횟수로 알립니다.
"""
import json
import sqlite3
import threading
import time


def _clean(value):
    """bytes 같은 원본 데이터가 기록에 섞이지 않게 바꿉니다."""
    if isinstance(value, (bytes, bytearray, memoryview)):
        return "<bytes omitted>"
    if isinstance(value, dict):
        return {str(k): _clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_clean(v) for v in value]
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    return str(value)


class EventLog:
    def __init__(self, path=":memory:", wall=time.time):
        self.wall = wall
        self.failures = 0
        self._lock = threading.Lock()
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.execute("CREATE TABLE IF NOT EXISTS events ("
                         "id INTEGER PRIMARY KEY AUTOINCREMENT, wall REAL NOT NULL, kind TEXT NOT NULL,"
                         " robot TEXT, detail TEXT NOT NULL)")
        self._db.commit()

    def record(self, kind, robot=None, detail=None, *, event_wall=None):
        """기록 성공 여부를 돌려줍니다. 실패해도 예외를 올리지 않습니다."""
        try:
            text = json.dumps(_clean(detail or {}), ensure_ascii=False, sort_keys=True)
            with self._lock:
                self._db.execute("INSERT INTO events (wall, kind, robot, detail) VALUES (?, ?, ?, ?)",
                                 (self.wall() if event_wall is None else event_wall, str(kind), robot, text))
                self._db.commit()
            return True
        except (sqlite3.Error, ValueError, TypeError):
            self.failures += 1
            return False

    def recent(self, limit=50):
        with self._lock:
            rows = self._db.execute("SELECT id, wall, kind, robot, detail FROM events ORDER BY id DESC LIMIT ?",
                                    (int(limit),)).fetchall()
        return [{"id": i, "wall": w, "kind": k, "robot": r, "detail": json.loads(d)} for i, w, k, r, d in rows]

    def close(self):
        with self._lock:
            self._db.close()
