"""Read complete A1M8 scans over USB or the robot's TCP relay."""

import argparse
import time
from contextlib import closing

from dashboard.lidar.rplidar_protocol import Command, SampleParser, parse_descriptor, request
from dashboard.lidar.scan_assembler import ScanAssembler
from dashboard.lidar.tcp_client import LidarClient, LidarHealthError


def read_exact(port, size):
    data = port.read(size)
    if len(data) != size:
        raise TimeoutError(f"LiDAR response: received {len(data)} of {size} bytes")
    return data


def expect_response(port, command, expected):
    port.write(request(command))
    header = parse_descriptor(read_exact(port, 7))
    if (header.size, header.mode, header.data_type) != expected:
        raise ValueError(f"Unexpected LiDAR response to {command:#x}: {header}")


def usb_samples(device):
    import serial

    port = serial.Serial(baudrate=115200, timeout=1, write_timeout=1)
    port.port = device
    port.dtr = True  # A1M8 USB adapter: asserted DTR stops the motor.
    port.open()
    try:
        port.write(request(Command.STOP))
        time.sleep(0.15)
        port.reset_input_buffer()
        expect_response(port, Command.GET_INFO, (20, 0, 4))
        info = read_exact(port, 20)
        print(f"model={info[0]} firmware={info[2]}.{info[1]} hardware={info[3]}")
        expect_response(port, Command.GET_HEALTH, (3, 0, 6))
        health = read_exact(port, 3)
        report_health(health[0], int.from_bytes(health[1:], "little"))
        if health[0] not in (0, 1):
            raise LidarHealthError("LiDAR failed its health check")

        port.dtr = False
        time.sleep(1)
        expect_response(port, Command.SCAN, (5, 1, 0x81))
        parser = SampleParser()
        while True:
            yield from parser.feed(port.read(256))
            # Give the caller a chance to enforce its deadline even on corrupt data.
            yield None
    finally:
        try:
            port.write(request(Command.STOP))
            port.flush()
        finally:
            try:
                port.dtr = True
                time.sleep(0.25)
            finally:
                port.close()
        print("USB STOP sent and COM port closed")


def report_health(status, code):
    print(f"health={status} code={code}")


def report_scans(samples, count, timeout):
    assembler = ScanAssembler()
    deadline = time.monotonic() + timeout
    received = 0
    with closing(samples):
        for sample in samples:
            if time.monotonic() >= deadline:
                break
            if sample is None:
                continue
            scan = assembler.add(sample)
            if scan is None:
                continue
            valid = sum(distance > 0 for distance in scan.distances_mm)
            received += 1
            print(f"scan={received} samples={len(scan.angles_deg)} valid={valid}")
            if received == count:
                return
    raise TimeoutError(f"Received {received} of {count} complete scans")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--usb", metavar="COM_PORT", help="Confirmed A1M8 USB adapter")
    mode.add_argument("--tcp", metavar="HOST", help="LiDAR relay address")
    parser.add_argument("--port", type=int, default=20108, help="TCP port")
    parser.add_argument("--scans", type=int, default=3)
    args = parser.parse_args()
    if args.scans < 1:
        parser.error("--scans must be positive")
    try:
        samples = (usb_samples(args.usb) if args.usb else
                   LidarClient(args.tcp, args.port, on_health=report_health).session())
        report_scans(samples, args.scans, timeout=12)
    except ModuleNotFoundError:
        parser.exit(1, "USB mode requires pyserial in the local test environment\n")
    except (OSError, ValueError) as error:
        parser.exit(1, f"LiDAR: {error}\n")


if __name__ == "__main__":
    main()
