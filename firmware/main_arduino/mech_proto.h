// 명령 메시지 해석 (docs/ai/protocol.md 2·3·4.4절). robot/proto.py 의 Arduino 이식.
// 하드웨어를 만지지 않는 순수 함수만 둡니다. 벤더·Arduino 비의존.
#ifndef MECH_PROTO_H
#define MECH_PROTO_H
#include <stdint.h>
#include <stddef.h>

namespace mech {

const int MAX_CMD_LEN = 64;
const long MAX_SEQ = 2147483647L;
const int PROTO_VERSION = 0;
const int MAX_TEL_LEN = 160;
const long ROLE_MIN_LEASE_MS = 100;
const long ROLE_MAX_LEASE_MS = 1000;
const char ROLE_PRIMARY = 'P', ROLE_SECONDARY = 'S', ROLE_NONE = 'N';

// 텔레메트리 warn 낱말 (6.1절 표 순서). 비트 번호 = 이 배열의 인덱스.
enum Warn {
  W_CLIPPED = 0, W_BUSY, W_LATCHED, W_MOVE_STALE, W_RESET_DENIED, W_GARBAGE, W_PROTO,
  W_BATT_LOW, W_BATT_UNKNOWN, W_IMU_UNKNOWN, W_PM_ON, W_LIDAR_UART, W_LIDAR_BACKLOG,
  WARN_COUNT
};
extern const char* const WARN_WORDS[WARN_COUNT];

enum CmdName { CMD_MOVE, CMD_STOP, CMD_ACTION, CMD_POSE, CMD_ESTOP, CMD_RESET, CMD_PING,
               CMD_HELLO, CMD_ROLE };

// parse() 결과 종류 (robot/proto.py 와 같은 의미)
enum ParseKind {
  PK_GARBAGE,  // 누구 것인지 모름 -> 버리고 warn=garbage
  PK_OTHER,    // 다른 로봇 것 -> 조용히 버림
  PK_BAD,      // 내 것인데 잘못됨 -> 정지 + 래치 bad_cmd
  PK_OK
};

struct Command {
  CmdName name;
  long seq = 0;        // HELLO 는 seq 자리에 boot_id(문자열, text)를 씀 -> seq 미사용
  long a0 = 0;         // MOVE step / HELLO proto / ROLE term
  long a1 = 0;         // MOVE angle / ROLE lease
  char code = 0;       // ROLE code
  char text[20] = {0}; // ACTION·POSE 토큰 / HELLO boot_id / ROLE session
  bool to_all = false;
};

// data[0..len) 를 해석해 out 을 채웁니다. robot_id 는 'A'/'B'.
ParseKind parse(const uint8_t* data, size_t len, char robot_id, Command& out);

// 범위로 자르기. 잘렸으면 cut=true.
long clip(long value, long lo, long hi, bool& cut);

// POSE 토큰 -> 동작 그룹 이름. "default" 는 nullptr 를 돌려주고 is_default=true.
const char* pose_to_action(const char* pose, bool& is_default);

}  // namespace mech
#endif
