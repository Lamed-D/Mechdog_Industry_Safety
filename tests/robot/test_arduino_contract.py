from pathlib import Path
import re
import unittest

from tests.robot import _env
import config
import proto


class ArduinoContractTests(unittest.TestCase):
    def test_shared_timing_keeps_safety_ordering_and_valid_role_lease(self):
        self.assertLessEqual(config.HOST_COMMAND_PERIOD_MS, 100)
        self.assertLess(config.HOST_TEL_FRESH_MS, config.LINK_TIMEOUT_MS)
        self.assertLess(config.ROLE_RENEW_MS, config.ROLE_LEASE_MS)
        self.assertLessEqual(proto.ROLE_MIN_LEASE_MS, config.ROLE_LEASE_MS)
        self.assertLessEqual(config.ROLE_LEASE_MS, proto.ROLE_MAX_LEASE_MS)

    def test_compile_skeleton_uses_same_protocol_constants(self):
        source = (Path(_env.ROOT) / "firmware/main_arduino/mech_config.h").read_text(encoding="utf-8")
        values = {name: int(value) for name, value in re.findall(r"^\s*\w+\s+(\w+)\s*=\s*(\d+)\s*;", source, re.M)}
        for name in ("LINK_TIMEOUT_MS", "WATCHDOG_PERIOD_MS", "CMD_PORT", "TEL_PORT", "LIDAR_TCP_PORT",
                     "LIDAR_BAUD", "LIDAR_RX_PIN", "LIDAR_TX_PIN"):
            self.assertEqual(values[name], getattr(config, name), name)
