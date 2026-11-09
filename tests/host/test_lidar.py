import socket
import threading
import unittest

from host.lidar.rplidar_protocol import (
    Command, Sample, SampleParser, parse_descriptor, parse_sample, request)
from host.lidar.scan_assembler import ScanAssembler
from host.lidar.tcp_client import LidarClient
from tools.mock.mock_lidar import MockLidar, descriptor, room_sample


class ProtocolTests(unittest.TestCase):
    def test_a1m8_synthetic_distance_limits(self):
        import random
        for index in range(360):
            sample = parse_sample(room_sample(index, noise_mm=100000,
                                              rng=random.Random(index)))
            self.assertGreaterEqual(sample.distance_mm, 150)
            self.assertLessEqual(sample.distance_mm, 12000)
        for noise in (float('nan'), float('inf'), -1):
            with self.assertRaises(ValueError):
                room_sample(0, noise_mm=noise)

    def test_commands(self):
        for command, value in [(Command.STOP, 0x25), (Command.RESET, 0x40),
                               (Command.SCAN, 0x20), (Command.GET_INFO, 0x50),
                               (Command.GET_HEALTH, 0x52)]:
            self.assertEqual(request(command), bytes([0xA5, value]))
        with self.assertRaises(ValueError):
            request(0xFF)

    def test_descriptor(self):
        result = parse_descriptor(b"\xa5\x5a\x05\x00\x00\x40\x81")
        self.assertEqual((result.size, result.mode, result.data_type), (5, 1, 129))
        for data in [b"", bytes(7), descriptor(0, 0, 6), descriptor(5, 3, 129)]:
            with self.assertRaises(ValueError):
                parse_descriptor(data)

    def test_known_sample(self):
        # Hand-calculated vector: quality 10, start, 90 degrees, 1000 mm.
        self.assertEqual(parse_sample(b"\x29\x01\x2d\xa0\x0f"),
                         Sample(True, 90, 1000, 10))
        self.assertEqual(parse_sample(b"\x02\x01\x00\x00\x00").distance_mm, 0)
        for data in [bytes(5), b"\x03\x01\x00\x00\x00",
                     b"\x02\x00\x00\x00\x00", b"\x02\x01\xb4\x00\x00"]:
            with self.assertRaises(ValueError):
                parse_sample(data)

    def test_fragmentation_and_resync(self):
        expected = [parse_sample(room_sample(i)) for i in range(30)]
        wire = bytes(7) + b"".join(room_sample(i) for i in range(30))
        for chunk_size in range(1, 19):
            parser = SampleParser()
            actual = []
            for offset in range(0, len(wire), chunk_size):
                actual.extend(parser.feed(wire[offset:offset + chunk_size]))
            self.assertEqual(actual, expected)
            self.assertEqual(parser.discarded_bytes, 7)
            self.assertLess(len(parser.buffer), 5)

    def test_corruption_and_midstream(self):
        parser = SampleParser()
        wire = room_sample(0)[3:] + bytes(8) + room_sample(1) + room_sample(2)
        self.assertEqual(parser.feed(wire), [parse_sample(room_sample(1)),
                                            parse_sample(room_sample(2))])
        parser.feed(bytes(100000))
        self.assertLess(len(parser.buffer), 5)


class AssemblyTests(unittest.TestCase):
    def test_boundaries_and_correction(self):
        assembler = ScanAssembler(10, -1)
        self.assertIsNone(assembler.add(Sample(False, 50, 1, 1)))
        self.assertIsNone(assembler.add(Sample(True, 0, 0, 0)))
        self.assertIsNone(assembler.add(Sample(False, 90, 2000, 10)))
        scan = assembler.add(Sample(True, 0, 3, 1))
        self.assertEqual(scan.angles_deg, (10, 280))
        self.assertEqual(scan.distances_mm, (0, 2000))

    def test_overflow_and_reset(self):
        assembler = ScanAssembler(max_samples=2)
        for start in (True, False, False):
            assembler.add(Sample(start, 0, 1, 1))
        self.assertIsNone(assembler.add(Sample(True, 0, 1, 1)))
        assembler.reset()
        self.assertIsNone(assembler.add(Sample(True, 0, 1, 1)))


class ClientTests(unittest.TestCase):
    def start_server(self, **kwargs):
        server = MockLidar(("127.0.0.1", 0), **kwargs)
        thread = threading.Thread(target=server.serve_forever,
                                  kwargs={"poll_interval": 0.01})
        thread.start()
        self.addCleanup(thread.join, 2)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return server

    def test_roundtrip(self):
        server = self.start_server(noise_mm=3)
        client = LidarClient(*server.server_address, timeout=1)
        assembler = ScanAssembler()
        session = client.session()
        try:
            for sample in session:
                scan = assembler.add(sample)
                if scan:
                    break
        finally:
            session.close()
        self.assertEqual(len(scan.angles_deg), 360)
        self.assertTrue(all(1997 <= d <= 2832 for d in scan.distances_mm))
        self.assertEqual(server.commands[:3], [0x25, 0x52, 0x20])

    def test_health_error_blocks_scan(self):
        server = self.start_server(health=2)
        with self.assertRaisesRegex(ValueError, "health"):
            list(LidarClient(*server.server_address, timeout=1).session())
        self.assertNotIn(0x20, server.commands)

    def test_disconnect_and_reconnect(self):
        server = self.start_server(disconnect_after=20, corrupt_every=5)
        stop = threading.Event()
        failures = []
        samples = []

        def disconnected(error):
            failures.append(error)
            if len(failures) == 2:
                stop.set()

        client = LidarClient(*server.server_address, timeout=1, retry_delay=0)
        client.run(samples.append, disconnected, stop)
        self.assertEqual(len(failures), 2)
        self.assertGreater(len(samples), 0)
        self.assertEqual(server.commands.count(0x52), 2)

    def test_idle_timeout(self):
        server = self.start_server(corrupt_every=1)
        with self.assertRaises(TimeoutError):
            list(LidarClient(*server.server_address, timeout=0.2).session())

    def test_fragmented_descriptor_with_stale_bytes(self):
        left, right = socket.socketpair()
        self.addCleanup(left.close)
        self.addCleanup(right.close)
        right.sendall(bytes(20) + descriptor(3, 0, 6))
        result = LidarClient("unused", timeout=0.3)._descriptor(
            left, (3, 0, 6), threading.Event())
        self.assertEqual(result.size, 3)

    def test_response_timeout_eof_and_cancellation(self):
        left, right = socket.socketpair()
        self.addCleanup(left.close)
        self.addCleanup(right.close)
        client = LidarClient("unused", timeout=0.05)
        stop = threading.Event()
        with self.assertRaises(TimeoutError):
            client._exact(left, 1, stop)
        stop.set()
        with self.assertRaises(InterruptedError):
            client._exact(left, 1, stop)
        stop.clear()
        right.close()
        with self.assertRaises(ConnectionError):
            client._exact(left, 1, stop)

    def test_cancelled_session_stops_without_scan(self):
        server = self.start_server()
        stop = threading.Event()
        stop.set()
        self.assertEqual(list(LidarClient(*server.server_address).session(stop)), [])
        self.assertNotIn(0x20, server.commands)
