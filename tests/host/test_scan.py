import math
import threading
import unittest
from host.lidar.laser_scan import ranges_metres
from host.lidar.scan_assembler import Scan
from host.lidar.rplidar_protocol import parse_sample
from host.lidar.tcp_client import LidarClient
from tools.mock.mock_lidar import room_sample
from tests.host import test_lidar


class ConversionTests(unittest.TestCase):
    def test_invalid_and_duplicate_bins(self):
        scan = Scan((0, 0, 1, 2, 3, 4), (2000, 1000, 0, 13000, 2000, 149), (1, 1, 1, 1, 0, 1))
        values = ranges_metres(scan)
        self.assertEqual(values[0], 1)
        self.assertTrue(all(math.isnan(v) for v in values[1:]))

    def test_boundaries_and_wrap(self):
        values = ranges_metres(Scan((360, -1), (150, 12000), (1, 1)))
        self.assertEqual((values[0], values[359]), (0.15, 12))

    def test_invalid_mock_sample_is_structurally_valid(self):
        sample = parse_sample(room_sample(0, invalid=True))
        self.assertTrue(sample.start)
        self.assertEqual((sample.distance_mm, sample.quality), (0, 0))


class HealthTests(unittest.TestCase):
    start_server = test_lidar.ClientTests.start_server
    def test_warning_is_reported(self):
        server = self.start_server(health=1)
        states = []
        session = LidarClient(*server.server_address, on_health=lambda *v: states.append(v)).session()
        try:
            next(session)
        finally:
            session.close()
        self.assertEqual(states, [(1, 0)])

    def test_error_stops_reconnect_without_reset(self):
        server = self.start_server(health=2)
        errors = []
        LidarClient(*server.server_address).run(lambda value: None, errors.append, threading.Event())
        self.assertEqual(len(errors), 1)
        self.assertNotIn(0x40, server.commands)
        self.assertEqual(server.commands.count(0x52), 1)
