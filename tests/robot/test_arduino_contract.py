from pathlib import Path
import re
import unittest

from tests.robot import _env
import config


class ArduinoContractTests(unittest.TestCase):
    def test_compile_skeleton_uses_same_protocol_constants(self):
        source = (Path(_env.ROOT) / "firmware/main_arduino/protocol_contract.h").read_text(encoding="utf-8")
        values = {name: int(value) for name, value in re.findall(r"constexpr\s+\w+\s+(\w+)\s*=\s*(\d+)", source)}
        for cpp, python in (("LINK_TIMEOUT_MS", "LINK_TIMEOUT_MS"), ("WATCHDOG_PERIOD_MS", "WATCHDOG_PERIOD_MS"),
                            ("COMMAND_PORT", "CMD_PORT"), ("TELEMETRY_PORT", "TEL_PORT"),
                            ("LIDAR_TCP_PORT", "LIDAR_TCP_PORT"), ("LIDAR_BAUD", "LIDAR_BAUD"),
                            ("LIDAR_RX_PIN", "LIDAR_RX_PIN"), ("LIDAR_TX_PIN", "LIDAR_TX_PIN")):
            self.assertEqual(values[cpp], getattr(config, python), cpp)
