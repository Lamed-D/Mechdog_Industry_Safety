"""Transport-independent v0 command scheduler. No networking or hardware at import."""
from dataclasses import dataclass
import math
import re
import secrets
import time

MAX_SEQ = 2147483647
WARN = {"clipped", "busy", "latched", "move_stale", "reset_denied", "garbage", "proto",
        "batt_low", "batt_unknown", "imu_unknown", "pm_on", "lidar_uart"}


def integer(value):
    if not re.fullmatch(r"[0-9]+", value):
        raise ValueError("invalid unsigned integer")
    return int(value)


@dataclass(frozen=True)
class Telemetry:
    robot: str
    tseq: int
    last_seq: int
    state: str
    latched: bool
    reason: str
    battery_mv: int | None
    tilt: tuple
    uptime_ms: int
    boot_id: str
    warnings: frozenset


def parse_telemetry(data):
    start = data.find(b"TEL|")
    end = data.find(b"$", start)
    if start < 0 or end < 0 or end - start + 1 > 160:
        raise ValueError("invalid telemetry framing")
    text = data[start:end + 1].decode("ascii")
    if any(ord(c) <= 32 for c in text):
        raise ValueError("invalid whitespace")
    fields = text.split("|")
    if len(fields) < 14 or fields[-1] != "$":
        raise ValueError("invalid telemetry field count")
    _, robot, tseq, seq, state, latched, reason, battery, x, y, uptime, boot, warn = fields[:13]
    if robot not in ("A", "B") or state not in ("idle", "moving", "action", "stopped"):
        raise ValueError("invalid robot or state")
    if latched not in ("0", "1") or reason not in ("none", "boot", "estop", "link_lost", "low_battery", "bad_cmd"):
        raise ValueError("invalid latch")
    if (latched == "1") != (state == "stopped") or (latched == "0") != (reason == "none"):
        raise ValueError("inconsistent latch state")
    if boot != "-" and not re.fullmatch(r"[a-zA-Z0-9]{1,16}", boot):
        raise ValueError("invalid boot id")
    volts = None if battery == "NA" else integer(battery)
    if volts is not None and volts <= 0:
        raise ValueError("invalid battery")
    tilt = []
    for value in (x, y):
        if value == "NA":
            tilt.append(None)
        elif re.fullmatch(r"-?[0-9]+(?:\.[0-9])?", value) and math.isfinite(float(value)):
            tilt.append(float(value))
        else:
            raise ValueError("invalid tilt")
    warnings = frozenset() if warn == "none" else frozenset(warn.split(","))
    if not warnings <= WARN or integer(seq) > MAX_SEQ:
        raise ValueError("invalid warnings or sequence")
    return Telemetry(robot, integer(tseq), integer(seq), state, latched == "1", reason,
                     volts, tuple(tilt), integer(uptime), boot, warnings)


class RobotLink:
    """Call step at >=10Hz. send(bytes) is injected; no implicit reset or movement."""
    def __init__(self, robot, send, *, clock=time.monotonic, boot_id=None, require_scan=True):
        if robot not in ("A", "B"):
            raise ValueError("unknown robot")
        self.robot, self.send, self.clock = robot, send, clock
        self.boot_id = boot_id or secrets.token_hex(8)
        if not re.fullmatch(r"[a-zA-Z0-9]{1,16}", self.boot_id):
            raise ValueError("invalid boot id")
        self.require_scan = require_scan
        self.latest = None
        self.last_seen = self.last_scan = -math.inf
        self.seq = 0
        self.next_send = self.next_hello = -math.inf
        self.intent = None
        self.emergency = False
        self.pending_reset = False
        self.last_acked = 0
        self.ack_wait_since = None
        self.fault = None

    def observe(self, data):
        value = parse_telemetry(data)
        if value.robot != self.robot:
            return False
        if value.boot_id != self.boot_id:
            self.latest = None
            self.intent = None
            self.pending_reset = False
            return False
        if self.latest and (value.tseq <= self.latest.tseq or value.uptime_ms < self.latest.uptime_ms):
            return False
        if value.last_seq > self.seq or value.last_seq < self.last_acked:
            self.intent = None
            return False
        now = self.clock()
        if self.latest is not None and now - self.last_seen >= 0.4:
            self._link_fault("telemetry_stale")
        if value.last_seq > self.last_acked:
            self.last_acked = value.last_seq
            self.ack_wait_since = None if value.last_seq == self.seq else now
        self.latest, self.last_seen = value, self.clock()
        self.seq = max(self.seq, value.last_seq)
        return True

    def _link_fault(self, reason):
        if not self.emergency:
            self.estop()
        self.fault = reason

    def mark_scan(self, valid):
        self.last_scan = self.clock() if valid else -math.inf
        if not valid:
            self.intent = None

    def move(self, step, angle):
        if any(isinstance(v, bool) or not isinstance(v, int) for v in (step, angle)):
            raise ValueError("integer motion only")
        if not (-100 <= step <= 100 and -30 <= angle <= 30):
            raise ValueError("motion out of range")
        self.intent = (step, angle, self.clock() + 0.3)

    def estop(self):
        self.emergency = True
        self.intent = None
        self.pending_reset = False
        self.next_send = -math.inf

    def stop(self):
        self.intent = None
        self.pending_reset = False
        self.next_send = -math.inf

    def request_reset(self):
        if not self.fresh() or not self.latest.latched or self.latest.battery_mv is None or self.latest.battery_mv < 6800:
            raise ValueError("reset requires fresh latched telemetry and adequate battery")
        self.emergency = False
        self.intent = None
        self.pending_reset = True
        self.next_send = -math.inf
        self.ack_wait_since = None
        self.fault = None

    def fresh(self):
        return self.latest is not None and 0 <= self.clock() - self.last_seen < 0.4

    def status(self):
        if self.latest is None or self.clock() - self.last_seen >= 1:
            return "unknown"
        return self.latest.state

    def _command(self, name, *args):
        if self.seq >= MAX_SEQ:
            self.emergency = True
            name, args = "ESTOP", ()
        else:
            self.seq += 1
        return ("CMD|%s|%s|%d|%s" % (name, self.robot, self.seq,
                "|".join(str(v) for v in args) + ("|" if args else "")) + "$").encode("ascii")

    def step(self):
        now = self.clock()
        if now < self.next_send:
            return
        self.next_send = now + 0.1  # No catch-up bursts.
        if self.latest is not None and not self.fresh():
            self._link_fault("telemetry_stale")
        if self.ack_wait_since is not None and now - self.ack_wait_since >= 0.6:
            self._link_fault("ack_stalled")
        if self.emergency:
            payload = self._command("ESTOP")
        elif not self.fresh():
            self.intent = None
            self.pending_reset = False
            if now >= self.next_hello:
                payload = ("CMD|HELLO|%s|%s|0|$" % (self.robot, self.boot_id)).encode()
                self.next_hello = now + 0.5
            else:
                payload = self._command("STOP")
        elif self.pending_reset:
            self.pending_reset = False
            payload = self._command("RESET")
        elif self.latest.latched:
            self.intent = None
            payload = self._command("PING")
        elif (self.intent and now < self.intent[2] and self.latest.state != "action"
              and self.latest.battery_mv is not None and self.latest.battery_mv >= 7000
              and not self.latest.warnings.intersection({"batt_unknown", "batt_low", "lidar_uart", "proto"})
              and (not self.require_scan or 0 <= now - self.last_scan < 0.3)):
            payload = self._command("MOVE", *self.intent[:2])
        else:
            self.intent = None
            payload = self._command("STOP")
        try:
            self.send(payload)
            if b"|HELLO|" not in payload and self.ack_wait_since is None:
                self.ack_wait_since = now
        except Exception:
            self._link_fault("send_failed")
            self.latest = None
            raise

    def close(self):
        self.intent = None
        self.send(self._command("STOP"))


def main():
    import argparse
    from host.udp_transport import UdpTransport
    parser = argparse.ArgumentParser(description="Status-only v0 link: HELLO/STOP, never RESET/MOVE")
    parser.add_argument("--robot", choices=("A", "B"), required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--receive-port", type=int, default=9101)
    parser.add_argument("--allow-real", action="store_true")
    args = parser.parse_args()
    transport = UdpTransport(args.host, receive_port=args.receive_port, allow_real=args.allow_real)
    link = RobotLink(args.robot, transport.send)
    try:
        while True:
            for data in transport.receive():
                try:
                    if link.observe(data):
                        print(link.robot, link.status(), "latched=", link.latest.latched)
                except ValueError:
                    link.intent = None
            link.step()
            time.sleep(0.02)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            link.close()
        finally:
            transport.close()


if __name__ == "__main__":
    main()
