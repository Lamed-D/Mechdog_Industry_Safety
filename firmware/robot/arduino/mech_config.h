// 로봇 설정값 (ai/protocol.md 8절). python/config.py 의 Arduino 이식.
// [가정] 값은 실측 전 초기값이며 Python 판과 같은 수를 씁니다. 두 펌웨어는 같은 규약·안전 동작을 지켜야 합니다.
// 이 헤더는 벤더·Arduino 에 의존하지 않습니다(안전 로직을 그 둘과 분리해 검토·시험하기 위함).
#ifndef MECH_CONFIG_H
#define MECH_CONFIG_H
#include <stdint.h>
#include <string.h>

namespace mech {

struct Config {
  char ROBOT_ID = 'A';  // 로봇 B 에 올릴 때 'B'. secrets.h 가 아니라 빌드 시 바꾼다.

  uint16_t CMD_PORT = 9100;
  uint16_t TEL_PORT = 9101;
  uint16_t LIDAR_TCP_PORT = 20108;

  uint32_t TEL_PERIOD_MS = 100;
  uint32_t WATCHDOG_PERIOD_MS = 20;  // 감시 주기, 50 ms 이하 (5.1절)
  uint32_t WIFI_RETRY_MS = 3000;     // Wi-Fi 재접속 시도 간격 [가정]

  uint32_t LINK_TIMEOUT_MS = 600;    // [가정]
  uint32_t MOVE_HOLD_MS = 600;       // [가정]

  int32_t LOW_BATT_WARN_MV = 7000;   // [가정] 셀당 3.5 V
  int32_t LOW_BATT_LATCH_MV = 6600;  // [가정] 셀당 3.3 V
  int32_t LOW_BATT_RESET_MV = 6800;  // [가정]
  uint32_t LOW_BATT_HOLD_MS = 2000;  // [가정]
  uint32_t BATT_UNKNOWN_HOLD_MS = 3000;  // [가정]
  uint32_t BATT_READ_PERIOD_MS = 200;

  uint32_t DEFAULT_POSE_SETTLE_MS = 600;  // [가정]
  uint32_t ACTION_MIN_MS = 200;           // 동작 시작 뒤 이 시간이 지나야 완료 확인을 믿음 [가정]

  // 라이다 원시 중계 (ai/protocol.md 7절)
  int LIDAR_UART_ID = 1;
  int LIDAR_RX_PIN = 32;
  int LIDAR_TX_PIN = 33;
  uint32_t LIDAR_BAUD = 115200;
  int LIDAR_RXBUF = 4096;            // [가정]
  uint32_t LIDAR_PENDING_WARN_MS = 100;  // [가정] TCP 로 보내지 못한 묶음의 나이

  // 동작 그룹 소요 시간 [가정]. 허용 목록(ai/protocol.md 3.3절)에 있는 이름만.
  // 최대 시간이며, 실제로는 완료 확인(run_status)이 먼저 끝낼 수 있습니다.
  uint32_t action_duration_ms(const char* name) const {
    if (strcmp(name, "stand_four_legs") == 0) return 2000;
    if (strcmp(name, "normal_attitude") == 0) return 2000;
    if (strcmp(name, "sit_dowm") == 0) return 3000;
    if (strcmp(name, "go_prone") == 0) return 3000;
    if (strcmp(name, "nodding_motion") == 0) return 3000;
    if (strcmp(name, "scrape_a_bow") == 0) return 4000;
    return 4000;  // 허용 목록 밖은 parse 에서 걸러지므로 도달하지 않음. 안전하게 최대값.
  }
};

}  // namespace mech
#endif
