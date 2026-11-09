"""사용자 Pi SQLite의 사건 메타데이터를 읽기 전용으로 JSON Lines 출력합니다."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3


def export_rows(path, limit=100):
    if not 1 <= limit <= 1000:
        raise ValueError("limit must be 1..1000")
    db = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)
    try:
        rows = db.execute("SELECT id, wall, robot, detail FROM events WHERE kind = ? ORDER BY id DESC LIMIT ?",
                          ("incident_context", limit))
        for identifier, wall, robot, detail in rows:
            context = json.loads(detail)
            yield {"v": 1, "origin": "pi_host", "event_id": identifier, "robot": robot,
                   "time_utc": datetime.fromtimestamp(wall, timezone.utc).isoformat(),
                   "evidence_source": context.get("detection", {}).get("source", "unknown"), "context": context}
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()
    if not args.db.is_file() or not 1 <= args.limit <= 1000:
        parser.error("기존 SQLite 파일과 1~1000건 범위가 필요합니다")
    for row in export_rows(args.db, args.limit):
        print(json.dumps(row, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
