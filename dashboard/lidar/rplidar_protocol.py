"""Standard scan wire format, independently implemented using public specs.

Protocol reference: https://github.com/Slamtec/rplidar_sdk/tree/master/sdk/include
The public SDK uses BSD-2-Clause; no SDK implementation is copied here.
Standard samples have no checksum: structural checks cannot detect all damage.
"""

from dataclasses import dataclass
from enum import IntEnum


class Command(IntEnum):
    STOP = 0x25
    RESET = 0x40
    SCAN = 0x20
    GET_INFO = 0x50
    GET_HEALTH = 0x52


def request(command):
    return bytes((0xA5, Command(command)))


@dataclass(frozen=True)
class Descriptor:
    size: int
    mode: int
    data_type: int


def parse_descriptor(data):
    if len(data) != 7 or data[:2] != b"\xa5\x5a":
        raise ValueError("invalid descriptor header")
    value = int.from_bytes(data[2:6], "little")
    result = Descriptor(value & 0x3fffffff, value >> 30, data[6])
    if result.size == 0 or result.mode not in (0, 1):
        raise ValueError("invalid descriptor size or mode")
    return result


@dataclass(frozen=True)
class Sample:
    start: bool
    angle_deg: float
    distance_mm: float
    quality: int


def parse_sample(data):
    if len(data) != 5:
        raise ValueError("sample must be five bytes")
    flags = data[0] & 3
    angle = int.from_bytes(data[1:3], "little")
    if flags not in (1, 2) or not angle & 1 or (angle >> 1) >= 360 * 64:
        raise ValueError("invalid sample flags or angle")
    return Sample(flags == 1, (angle >> 1) / 64,
                  int.from_bytes(data[3:5], "little") / 4, data[0] >> 2)


class SampleParser:
    """Incremental parser; reject one byte at a time to recover alignment."""

    def __init__(self):
        self.buffer = bytearray()
        self.discarded_bytes = 0

    def feed(self, data):
        self.buffer.extend(data)
        samples = []
        offset = 0
        while len(self.buffer) - offset >= 5:
            try:
                sample = parse_sample(self.buffer[offset:offset + 5])
            except ValueError:
                offset += 1
                self.discarded_bytes += 1
            else:
                samples.append(sample)
                offset += 5
        del self.buffer[:offset]
        return samples
