#pragma once
#include <stdint.h>

namespace mechdog_contract {
constexpr uint32_t LINK_TIMEOUT_MS = 600;
constexpr uint32_t WATCHDOG_PERIOD_MS = 20;
constexpr uint16_t COMMAND_PORT = 9100;
constexpr uint16_t TELEMETRY_PORT = 9101;
constexpr uint16_t LIDAR_TCP_PORT = 20108;
constexpr uint32_t LIDAR_BAUD = 115200;
constexpr int LIDAR_RX_PIN = 32;
constexpr int LIDAR_TX_PIN = 33;
constexpr uint32_t ROLE_LEASE_MS = 1000;
static_assert(WATCHDOG_PERIOD_MS <= 50, "watchdog must yield within 50ms");
}  // namespace mechdog_contract
