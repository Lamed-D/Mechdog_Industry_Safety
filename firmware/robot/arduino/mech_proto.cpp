// python/proto.py 의 Arduino 이식. 동작·분기를 Python 판과 1:1 로 맞춥니다.
#include "mech_proto.h"
#include <string.h>

namespace mech {

const char* const WARN_WORDS[WARN_COUNT] = {
  "clipped", "busy", "latched", "move_stale", "reset_denied", "garbage", "proto",
  "batt_low", "batt_unknown", "imu_unknown", "pm_on", "lidar_uart", "lidar_backlog"};

static const char* ACTION_ALLOW[] = {
  "stand_four_legs", "normal_attitude", "sit_dowm", "go_prone", "nodding_motion", "scrape_a_bow"};

namespace {

struct Tok { const char* p; size_t n; };

bool tok_eq(const Tok& t, const char* s) {
  size_t n = strlen(s);
  return t.n == n && memcmp(t.p, s, n) == 0;
}

// 토큰을 널 종료 문자열로 복사(최대 cap-1). 넘치면 false.
bool tok_copy(const Tok& t, char* dst, size_t cap) {
  if (t.n >= cap) return false;
  memcpy(dst, t.p, t.n);
  dst[t.n] = 0;
  return true;
}

enum PInt { PI_BAD, PI_OK, PI_OVER };

// 10진 정수. 부호 '-'만 허용, '+'·소수점·공백·빈 값은 PI_BAD. int32 범위를 넘으면 PI_OVER(값은 포화).
PInt parse_int(const char* s, size_t n, long& out) {
  if (n == 0) return PI_BAD;
  bool neg = s[0] == '-';
  size_t i = neg ? 1 : 0;
  if (i == n) return PI_BAD;
  unsigned long long acc = 0;
  bool over = false;
  for (; i < n; i++) {
    char c = s[i];
    if (c < '0' || c > '9') return PI_BAD;
    acc = acc * 10 + (unsigned)(c - '0');
    if (acc > 2147483647ULL) { over = true; acc = 2147483647ULL; }
  }
  out = neg ? -(long)acc : (long)acc;
  return over ? PI_OVER : PI_OK;
}

bool is_boot_id(const char* s, size_t n) {
  if (n < 1 || n > 16) return false;
  for (size_t i = 0; i < n; i++) {
    char c = s[i];
    if (!((c >= '0' && c <= '9') || (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z')))
      return false;
  }
  return true;
}

bool action_allowed(const char* name) {
  for (size_t i = 0; i < sizeof(ACTION_ALLOW) / sizeof(ACTION_ALLOW[0]); i++)
    if (strcmp(name, ACTION_ALLOW[i]) == 0) return true;
  return false;
}

// 이름 -> (seq 뒤) 인자 개수. 모르는 이름이면 -1.
int arg_count(const Tok& name, CmdName& out) {
  if (tok_eq(name, "MOVE"))   { out = CMD_MOVE;   return 2; }
  if (tok_eq(name, "STOP"))   { out = CMD_STOP;   return 0; }
  if (tok_eq(name, "ACTION")) { out = CMD_ACTION; return 1; }
  if (tok_eq(name, "POSE"))   { out = CMD_POSE;   return 1; }
  if (tok_eq(name, "ESTOP"))  { out = CMD_ESTOP;  return 0; }
  if (tok_eq(name, "RESET"))  { out = CMD_RESET;  return 0; }
  if (tok_eq(name, "PING"))   { out = CMD_PING;   return 0; }
  if (tok_eq(name, "HELLO"))  { out = CMD_HELLO;  return 1; }
  if (tok_eq(name, "ROLE"))   { out = CMD_ROLE;   return 4; }
  return -1;
}

}  // namespace

long clip(long value, long lo, long hi, bool& cut) {
  if (value < lo) { cut = true; return lo; }
  if (value > hi) { cut = true; return hi; }
  cut = false;
  return value;
}

const char* pose_to_action(const char* pose, bool& is_default) {
  is_default = false;
  if (strcmp(pose, "default") == 0) { is_default = true; return nullptr; }
  if (strcmp(pose, "sit") == 0) return "sit_dowm";
  if (strcmp(pose, "prone") == 0) return "go_prone";
  return nullptr;  // parse 에서 걸러지므로 도달하지 않음
}

ParseKind parse(const uint8_t* data, size_t len, char robot_id, Command& out) {
  if (len == 0) return PK_GARBAGE;

  // "CMD" 찾기
  size_t start = (size_t)-1;
  for (size_t i = 0; i + 3 <= len; i++) {
    if (data[i] == 'C' && data[i + 1] == 'M' && data[i + 2] == 'D') { start = i; break; }
  }
  if (start == (size_t)-1) return PK_GARBAGE;
  // start 뒤 첫 '$'
  size_t end = (size_t)-1;
  for (size_t i = start; i < len; i++) {
    if (data[i] == '$') { end = i; break; }
  }
  if (end == (size_t)-1) return PK_GARBAGE;

  const char* raw = (const char*)(data + start);
  size_t raw_len = end - start + 1;  // '$' 포함

  // '|' 로 나누기
  const int MAX_TOK = 12;
  Tok tok[MAX_TOK];
  int ntok = 0;
  size_t fstart = 0;
  for (size_t i = 0; i <= raw_len; i++) {
    if (i == raw_len || raw[i] == '|') {
      if (ntok >= MAX_TOK) return PK_GARBAGE;  // 너무 많은 필드
      tok[ntok].p = raw + fstart;
      tok[ntok].n = i - fstart;
      ntok++;
      fstart = i + 1;
    }
  }
  if (ntok < 4) return PK_GARBAGE;
  if (!(tok[ntok - 1].n == 1 && tok[ntok - 1].p[0] == '$')) return PK_GARBAGE;

  // target = tok[2]
  Tok target = tok[2];
  for (size_t i = 0; i < target.n; i++)
    if ((uint8_t)target.p[i] >= 128) return PK_GARBAGE;  // 디코드 실패 취급
  bool mine = target.n == 1 && target.p[0] == robot_id;
  bool all = target.n == 1 && target.p[0] == '*';
  if (!mine && !all) return PK_OTHER;

  // 여기부터 내 것(또는 전체) -> 문제가 있으면 BAD
  if (raw_len > (size_t)MAX_CMD_LEN) return PK_BAD;
  for (size_t i = 0; i < raw_len; i++) {
    uint8_t b = (uint8_t)raw[i];
    if (b >= 128 || b <= 32) return PK_BAD;
  }

  // fields = tok[1 .. ntok-2]
  int nfields = ntok - 2;  // 'CMD' 와 '$' 제외
  Tok name = tok[1];
  CmdName cmd;
  int count = arg_count(name, cmd);
  if (count < 0 || nfields != 3 + count) return PK_BAD;

  bool to_all = all;
  if (to_all && !(cmd == CMD_STOP || cmd == CMD_ESTOP)) return PK_BAD;

  // args = tok[4 .. ], seq/boot_id = tok[3]
  Tok seqtok = tok[3];
  Tok a[4];
  for (int i = 0; i < count; i++) a[i] = tok[4 + i];

  out = Command();
  out.name = cmd;
  out.to_all = to_all;

  if (cmd == CMD_HELLO) {
    long proto;
    PInt pk = parse_int(a[0].p, a[0].n, proto);
    if (!is_boot_id(seqtok.p, seqtok.n) || pk == PI_BAD) return PK_BAD;
    if (!tok_copy(seqtok, out.text, sizeof(out.text))) return PK_BAD;
    out.a0 = proto;
    return PK_OK;
  }

  long seq;
  if (parse_int(seqtok.p, seqtok.n, seq) != PI_OK || seq < 0 || seq > MAX_SEQ) return PK_BAD;
  out.seq = seq;

  if (cmd == CMD_MOVE) {
    long step, angle;
    if (parse_int(a[0].p, a[0].n, step) == PI_BAD) return PK_BAD;
    if (parse_int(a[1].p, a[1].n, angle) == PI_BAD) return PK_BAD;
    out.a0 = step;
    out.a1 = angle;
  } else if (cmd == CMD_ACTION) {
    if (!tok_copy(a[0], out.text, sizeof(out.text)) || !action_allowed(out.text)) return PK_BAD;
  } else if (cmd == CMD_POSE) {
    if (!tok_copy(a[0], out.text, sizeof(out.text))) return PK_BAD;
    if (!(strcmp(out.text, "default") == 0 || strcmp(out.text, "sit") == 0 ||
          strcmp(out.text, "prone") == 0))
      return PK_BAD;
  } else if (cmd == CMD_ROLE) {
    // args = session, term, code, lease
    long term, lease;
    if (!is_boot_id(a[0].p, a[0].n)) return PK_BAD;
    if (parse_int(a[1].p, a[1].n, term) != PI_OK || term < 1 || term > MAX_SEQ) return PK_BAD;
    if (!(a[2].n == 1 && (a[2].p[0] == ROLE_PRIMARY || a[2].p[0] == ROLE_SECONDARY ||
                          a[2].p[0] == ROLE_NONE)))
      return PK_BAD;
    if (parse_int(a[3].p, a[3].n, lease) != PI_OK ||
        lease < ROLE_MIN_LEASE_MS || lease > ROLE_MAX_LEASE_MS)
      return PK_BAD;
    if (!tok_copy(a[0], out.text, sizeof(out.text))) return PK_BAD;
    out.a0 = term;
    out.code = a[2].p[0];
    out.a1 = lease;
  }
  return PK_OK;
}

}  // namespace mech
