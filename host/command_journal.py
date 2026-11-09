"""동기화 작업자 전용 처리 ID 저널. 디스크 작업을 제어 잠금 안에서 호출하지 않습니다."""
from dataclasses import asdict
import hashlib
import json
import re
import sqlite3
from host.command_envelope import Command


def _fingerprint(command):
    if not isinstance(command, Command) or command.kind not in ("reset", "operator"):
        raise ValueError("journal is for validated non-estop commands")
    data = json.dumps(asdict(command), sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


class CommandJournal:
    """실행 전에 예약을 커밋합니다. 예약 상태의 재전달/재시작은 재실행하지 않습니다."""
    def __init__(self, path, capacity=100_000):
        if type(capacity) is not int or not 1 <= capacity <= 100_000:
            raise ValueError("invalid journal capacity")
        self.capacity = capacity
        self._db = sqlite3.connect(path, timeout=.05, isolation_level=None)
        try:
            self._db.execute("PRAGMA journal_mode=WAL")
            self._db.execute("PRAGMA synchronous=FULL")
            self._db.execute("CREATE TABLE IF NOT EXISTS command_journal ("
                             "hub TEXT NOT NULL, id TEXT NOT NULL, digest TEXT NOT NULL,"
                             "status TEXT NOT NULL, reason TEXT NOT NULL, PRIMARY KEY(hub,id))")
        except Exception:
            self._db.close()
            raise

    def _row(self, command, digest):
        row = self._db.execute("SELECT digest,status,reason FROM command_journal WHERE hub=? AND id=?",
                               (command.hub_id, command.id)).fetchone()
        if row is not None and row[0] != digest:
            raise ValueError("command id reused with different envelope")
        return row

    def claim(self, command):
        digest = _fingerprint(command)
        self._db.execute("BEGIN IMMEDIATE")
        try:
            if self._row(command, digest) is not None:
                self._db.execute("COMMIT")
                return False
            if self._db.execute("SELECT COUNT(*) FROM command_journal").fetchone()[0] >= self.capacity:
                raise ValueError("journal full; non-stop commands denied")
            self._db.execute("INSERT INTO command_journal VALUES (?,?,?,'reserved','awaiting_result')",
                             (command.hub_id, command.id, digest))
            self._db.execute("COMMIT")
            return True
        except Exception:
            if self._db.in_transaction:
                self._db.execute("ROLLBACK")
            raise

    def complete(self, command, status, reason="none"):
        digest = _fingerprint(command)
        if status not in ("done", "rejected", "failed") or not isinstance(reason, str) or not re.fullmatch(r"[a-z0-9_]{1,64}", reason):
            raise ValueError("invalid journal result")
        self._db.execute("BEGIN IMMEDIATE")
        try:
            row = self._row(command, digest)
            if row is None or row[1] != "reserved":
                raise ValueError("command is not reserved")
            self._db.execute("UPDATE command_journal SET status=?,reason=? WHERE hub=? AND id=?",
                             (status, reason, command.hub_id, command.id))
            self._db.execute("COMMIT")
        except Exception:
            if self._db.in_transaction:
                self._db.execute("ROLLBACK")
            raise

    def result(self, command):
        row = self._row(command, _fingerprint(command))
        return None if row is None else {"status": row[1], "reason": row[2]}

    def close(self):
        self._db.close()
