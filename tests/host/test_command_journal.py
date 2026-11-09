from dataclasses import replace
from pathlib import Path
import sqlite3
import tempfile
import unittest
from host.command_envelope import Command
from host.command_journal import CommandJournal


class JournalTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[2] / "build"
        root.mkdir(exist_ok=True)
        self.directory = tempfile.TemporaryDirectory(dir=root)
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "commands.db"
        self.command = Command("00000000-0000-4000-8000-000000000001", "hub-test", "device-test", "A", "reset", 0, 10,
                               (("confirmed", True), ("reset_context", "0" * 32 + ":1")))

    def open(self, **kwargs):
        journal = CommandJournal(self.path, **kwargs)
        self.addCleanup(journal.close)
        return journal

    def test_reserved_command_survives_restart_without_reexecution(self):
        journal = CommandJournal(self.path)
        self.assertTrue(journal.claim(self.command))
        journal.close()  # 실행 전/도중 비정상 종료를 재현
        restarted = self.open()
        self.assertFalse(restarted.claim(self.command))
        self.assertEqual(restarted.result(self.command)["status"], "reserved")

    def test_completion_and_duplicate_result_are_stable(self):
        journal = self.open()
        self.assertTrue(journal.claim(self.command))
        journal.complete(self.command, "done")
        self.assertFalse(journal.claim(self.command))
        self.assertEqual(journal.result(self.command), {"status": "done", "reason": "none"})
        with self.assertRaises(ValueError):
            journal.complete(self.command, "failed")

    def test_id_reuse_with_changed_target_or_payload_is_rejected(self):
        journal = self.open()
        journal.claim(self.command)
        for changed in (replace(self.command, robot_id="B"), replace(self.command, payload=())):
            with self.subTest(changed=changed), self.assertRaisesRegex(ValueError, "reused"):
                journal.claim(changed)

    def test_two_connections_only_claim_once(self):
        first, second = self.open(), self.open()
        self.assertTrue(first.claim(self.command))
        self.assertFalse(second.claim(self.command))

    def test_capacity_disk_failure_and_estop_cannot_grant_execution(self):
        journal = self.open(capacity=1)
        journal.claim(self.command)
        with self.assertRaisesRegex(ValueError, "full"):
            journal.claim(replace(self.command, id="second"))
        with self.assertRaises(ValueError):
            journal.claim(replace(self.command, kind="estop"))
        journal._db.execute("PRAGMA query_only=ON")
        with self.assertRaises(sqlite3.Error):
            journal.complete(self.command, "done")
        with self.assertRaises(sqlite3.Error):
            journal.claim(self.command)
        self.assertEqual(journal.result(self.command)["status"], "reserved")

    def test_unknown_or_unstructured_completion_is_rejected(self):
        journal = self.open()
        with self.assertRaises(ValueError):
            journal.complete(self.command, "done")
        journal.claim(self.command)
        with self.assertRaises(ValueError):
            journal.complete(self.command, "failed", "arbitrary details / secrets")
