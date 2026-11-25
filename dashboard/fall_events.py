"""Local event archive. Each event owns exactly two annotated JPEGs."""
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
from time import time


DATA_DIR = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "MechDog"
VERDICTS = ("미검토", "쓰러짐 확인", "오탐", "판단 보류")


class FallEvents:
    def __init__(self, path=None):
        self.path = path or DATA_DIR / "fall-events.sqlite3"

    def last_detection(self, robot):
        if self.path.exists():
            with closing(sqlite3.connect(self.path)) as db:
                return db.execute("SELECT max(detected) FROM event WHERE robot=?", (robot,)).fetchone()[0]

    def prepare(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path)) as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS event (
                    id INTEGER PRIMARY KEY, robot TEXT NOT NULL, detected REAL NOT NULL,
                    verdict TEXT NOT NULL DEFAULT '미검토', note TEXT NOT NULL DEFAULT '',
                    reviewed REAL
                );
                CREATE TABLE IF NOT EXISTS photo (
                    event_id INTEGER NOT NULL REFERENCES event(id), position INTEGER NOT NULL,
                    received REAL NOT NULL, width INTEGER NOT NULL, height INTEGER NOT NULL,
                    box TEXT NOT NULL, jpeg BLOB NOT NULL, PRIMARY KEY(event_id, position)
                );
            """)

    def record(self, robot, first, second):
        with closing(sqlite3.connect(self.path)) as db, db:
            event = db.execute("INSERT INTO event(robot, detected) VALUES (?, ?)",
                               (robot, second[0])).lastrowid
            for index, (received, width, height, box, jpeg) in enumerate((first, second)):
                db.execute("INSERT INTO photo VALUES (?, ?, ?, ?, ?, ?, ?)",
                           (event, index, received, width, height, json.dumps(box), jpeg))

    def page(self, before):
        if not self.path.exists():
            return []
        with closing(sqlite3.connect(self.path)) as db:
            db.row_factory = sqlite3.Row
            rows = db.execute("SELECT * FROM event WHERE id < ? ORDER BY id DESC LIMIT 25",
                              (before,))
            events = []
            for row in rows:
                event = dict(row)
                photos = db.execute("SELECT received, width, height, box FROM photo "
                                    "WHERE event_id = ? ORDER BY position", (row["id"],))
                event["photos"] = [dict(photo, box=json.loads(photo["box"])) for photo in photos]
                events.append(event)
            return events

    def photo(self, event, position):
        if self.path.exists():
            with closing(sqlite3.connect(self.path)) as db:
                row = db.execute("SELECT jpeg FROM photo WHERE event_id=? AND position=?",
                                 (event, position)).fetchone()
                if row:
                    return row[0]
        raise KeyError(event)

    def review(self, event, verdict, note):
        if verdict not in VERDICTS[1:] or not isinstance(note, str) or len(note) > 1000:
            raise ValueError("판정을 선택하고 메모는 1000자 이내로 입력하세요.")
        if not self.path.exists():
            raise KeyError(event)
        with closing(sqlite3.connect(self.path)) as db, db:
            updated = db.execute("UPDATE event SET verdict=?, note=?, reviewed=? WHERE id=?",
                                 (verdict, note, time(), event))
            if not updated.rowcount:
                raise KeyError(event)
