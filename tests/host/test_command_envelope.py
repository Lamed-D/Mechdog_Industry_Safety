import json
import unittest
from datetime import datetime, timezone
from host.command_envelope import ReplayWindow, validate_envelope

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp()


class EnvelopeTests(unittest.TestCase):
    def row(self, **updates):
        row = dict(v=1, id="00000000-0000-4000-8000-000000000001", hub_id="hub-test",
                   device_id="device-test", robot_id="A", kind="reset", payload={"confirmed": True},
                   created_at="2026-01-01T00:00:00Z", expires_at="2026-01-01T00:00:10Z")
        row.update(updates)
        return row

    def validate(self, row=None, **kwargs):
        args = dict(hub_id="hub-test", authenticated_device="device-test",
                    permissions=("estop", "reset", "operator"), now_utc=NOW,
                    clock_trusted=True, operator_events=("operator_ack",))
        args.update(kwargs)
        return validate_envelope(json.dumps(self.row() if row is None else row).encode(), **args)

    def test_reset_and_payload_copy(self):
        row = self.row()
        command = self.validate(row)
        row["payload"]["confirmed"] = False
        self.assertEqual(command.payload, (("confirmed", True),))
        self.assertEqual(command.robot_id, "A")

    def test_delay_expiry_future_and_untrusted_clock_reject_reset(self):
        for changes in (dict(now_utc=NOW + 10), dict(now_utc=NOW - .001),
                        dict(clock_trusted=False), dict(now_utc=float("nan"))):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.validate(**changes)

    def test_expired_estop_with_bad_clock_is_still_accepted(self):
        command = self.validate(self.row(kind="estop", robot_id=None, payload={}),
                                now_utc=NOW + 100, clock_trusted=False)
        self.assertEqual(command.kind, "estop")

    def test_untrusted_identity_or_permission_never_comes_from_payload(self):
        for changes in (dict(authenticated_device="other"), dict(hub_id="other"), dict(permissions=())):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.validate(**changes)
        for updates in (dict(kind="MOVE"), dict(robot_id="primary"), dict(payload={"confirmed": 1}),
                        dict(payload={"confirmed": False}), dict(payload={"confirmed": True, "admin": True}),
                        dict(v=True), dict(v=2), dict(expires_at="2026-01-01T00:00:11Z"),
                        dict(created_at="2026-01-01"), dict(expires_at="2026-01-01T00:00:00Z"),
                        dict(id="bad"), dict(id=1)):
            with self.subTest(updates=updates), self.assertRaises(ValueError):
                self.validate(self.row(**updates))

    def test_operator_requires_separate_allowlist(self):
        row = self.row(kind="operator", robot_id=None, payload={"event": "operator_ack"})
        self.assertEqual(self.validate(row).payload, (("event", "operator_ack"),))
        with self.assertRaises(ValueError):
            self.validate(row, operator_events=())

    def test_invalid_raw_size_json_and_duplicate_keys(self):
        args = dict(hub_id="hub-test", authenticated_device="device-test", permissions=(), now_utc=NOW)
        for raw in (b"", b"x" * 4097, b"[]", b"\xff", b"{", b'{"v":1,"v":1}'):
            with self.subTest(raw=raw[:20]), self.assertRaises(ValueError):
                validate_envelope(raw, **args)

    def test_replay_window_fails_closed_when_full_and_does_not_block_estop(self):
        now = [0]
        window = ReplayWindow(capacity=1, clock=lambda: now[0])
        command = self.validate()
        self.assertTrue(window.admit(command))
        self.assertFalse(window.admit(command))
        other = self.validate(self.row(id="00000000-0000-4000-8000-000000000002"))
        with self.assertRaisesRegex(ValueError, "full"):
            window.admit(other)
        estop = self.validate(self.row(kind="estop", robot_id=None, payload={}))
        self.assertTrue(window.admit(estop))
        self.assertTrue(window.admit(estop))
        now[0] = 10
        self.assertTrue(window.admit(other))
        now[0] = 9
        with self.assertRaisesRegex(ValueError, "clock"):
            window.admit(command)
