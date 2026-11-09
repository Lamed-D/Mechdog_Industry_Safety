"""실물 확인 4 (PC·Pi 5 쪽): 로봇의 b4_wifi_echo.py 에 UDP 를 10 Hz 로 보내 왕복 지연을 잽니다.

    python tools/bringup/rtt_probe.py <로봇IP> [--count 300] [--port 9100]

LINK_TIMEOUT_MS(600 ms, docs/protocol.md 5.1절)를 정할 근거가 되는 값을 보여 줍니다.
로봇을 움직이는 명령은 보내지 않습니다(되돌려 보내기 전용 문자열).
"""

import argparse
import socket
import time


def percentile(values, ratio):
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round(ratio * (len(ordered) - 1))))
    return ordered[index]


def summarize(rtts_ms, sent, gaps_ms, timeout_ms=600):
    lost = sent - len(rtts_ms)
    return {
        "sent": sent,
        "received": len(rtts_ms),
        "lost": lost,
        "p50_ms": percentile(rtts_ms, 0.5),
        "p95_ms": percentile(rtts_ms, 0.95),
        "p99_ms": percentile(rtts_ms, 0.99),
        "max_ms": max(rtts_ms) if rtts_ms else None,
        "longest_gap_ms": max(gaps_ms) if gaps_ms else None,
        "gaps_over_timeout": sum(1 for gap in gaps_ms if gap > timeout_ms),
    }


def probe(host, port, count, period_s=0.1, wait_s=1.0):
    if count <= 0 or period_s <= 0 or wait_s <= 0:
        raise ValueError("probe timing and count must be positive")
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(0.01)
    sent_at = {}
    rtts = []
    arrivals = []
    next_send = time.monotonic()
    seq = 0
    deadline = None
    while True:
        now = time.monotonic()
        if seq < count and now >= next_send:
            seq += 1
            sent_at[seq] = now
            sock.sendto(("ECHO|%d|$" % seq).encode(), (host, port))
            next_send += period_s
            if seq == count:
                deadline = now + wait_s
        if deadline is not None and now > deadline:
            break
        try:
            data, _addr = sock.recvfrom(128)
        except OSError:
            continue
        try:
            number = int(data.decode().split("|")[1])
        except (ValueError, IndexError, UnicodeDecodeError):
            continue
        start = sent_at.pop(number, None)
        if start is not None:
            arrived = time.monotonic()
            rtts.append((arrived - start) * 1000)
            arrivals.append(arrived)
    gaps = [(b - a) * 1000 for a, b in zip(arrivals, arrivals[1:])]
    return summarize(rtts, seq, gaps)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("host")
    parser.add_argument("--port", type=int, default=9100)
    parser.add_argument("--count", type=int, default=300)
    args = parser.parse_args()
    for key, value in probe(args.host, args.port, args.count).items():
        print("%-18s %s" % (key, "%.1f" % value if isinstance(value, float) else value))


if __name__ == "__main__":
    main()
