// firmware/main_arduino 이식성 코어(mech_core 등)의 행위 테스트.
// robot/ Python 판의 tests/robot 시나리오를 C++ 로 옮겨, 포팅이 같은 안전 동작을 하는지 확인합니다.
// 하드웨어·Arduino·벤더 없이 표준 C++ 로 돌립니다(가짜 Clock·Motion·Sensors 주입).
//
// 실행: 호스트 C++ 컴파일러로 빌드. 저장소 루트에서
//   g++ -std=c++17 -Ifirmware/main_arduino tests/firmware/test_core.cpp -o test_core && ./test_core
// 컴파일러가 없으면 tools/test_main_arduino.py 가 Docker(gcc) 로 대신 돌립니다.
#include <cstdio>
#include <cstring>

// 유니티 빌드: 코어 .cpp 를 함께 묶어 한 번에 컴파일.
#include "mech_proto.cpp"
#include "mech_roles.cpp"
#include "mech_core.cpp"

using namespace mech;

static int g_fail = 0, g_total = 0;
#define CHECK(cond)                                                              \
  do {                                                                           \
    g_total++;                                                                   \
    if (!(cond)) { g_fail++; printf("  FAIL %s:%d  %s\n", __func__, __LINE__, #cond); } \
  } while (0)

struct TestClock : Clock {
  uint32_t t = 1000;
  uint32_t ticks_ms() override { return t; }
  void advance(uint32_t ms) { t += ms; }
};

struct RecMotion : MotionBackend {
  int stops = 0, moves = 0, default_poses = 0, actions = 0;
  long last_step = 0, last_angle = 0;
  char last_action[20] = {0};
  bool over = true;  // action_over 가 돌려줄 값
  void stop() override { stops++; }
  void move(long s, long a) override { moves++; last_step = s; last_angle = a; }
  void action(const char* n) override { actions++; strncpy(last_action, n, sizeof(last_action) - 1); }
  void stop_action() override {}
  bool action_over() override { return over; }
  void default_pose() override { default_poses++; }
};

struct TestSensors : Sensors {
  bool batt_known = true;
  int32_t batt = 7400;
  bool tilt_known = true;
  bool read_battery(int32_t& mv) override { if (!batt_known) return false; mv = batt; return true; }
  bool read_tilt(float& x, float& y) override { if (!tilt_known) return false; x = 1.2f; y = -0.4f; return true; }
};

static void feed(Robot& r, const char* s, uint32_t ip = 0x0100007f) {
  r.handle((const uint8_t*)s, strlen(s), ip);
}
static bool tel_has(Robot& r, const char* needle) {
  char line[200];
  size_t n = r.telemetry(line, sizeof(line));
  if (n == 0) return false;
  return strstr(line, needle) != nullptr;
}

// --- 부팅: 사람이 RESET 하기 전까지 래치(boot) ---
static void test_boot_latched() {
  TestClock c; RecMotion m; TestSensors s; Config cfg; Robot r(cfg, &m, &c, &s);
  CHECK(tel_has(r, "|stopped|1|boot|"));
}

// --- boot_id 모르면 STOP·ESTOP 만. MOVE 는 무시 ---
static void test_before_boot_id() {
  TestClock c; RecMotion m; TestSensors s; Config cfg; Robot r(cfg, &m, &c, &s);
  feed(r, "CMD|MOVE|A|5|40|0|$");
  CHECK(m.moves == 0);
  feed(r, "CMD|ESTOP|A|1|$");  // boot_id 몰라도 ESTOP 은 실행
  CHECK(tel_has(r, "|estop|"));
}

// --- HELLO → RESET → MOVE 정상 흐름 ---
static void test_hello_reset_move() {
  TestClock c; RecMotion m; TestSensors s; Config cfg; Robot r(cfg, &m, &c, &s);
  feed(r, "CMD|HELLO|A|boot1|0|$");
  CHECK(tel_has(r, "|boot1|"));        // boot_id 보고
  r.tick(true);                         // wifi_ok·battery 확보
  CHECK(tel_has(r, "|stopped|1|boot|"));
  feed(r, "CMD|RESET|A|1|$");
  CHECK(tel_has(r, "|idle|0|none|"));  // 해제됨, 그러나 아직 안 움직임
  CHECK(m.moves == 0);
  feed(r, "CMD|MOVE|A|2|40|-10|$");
  CHECK(m.moves == 1 && m.last_step == 40 && m.last_angle == -10);
  CHECK(tel_has(r, "|moving|0|none|"));
}

// --- 늦게 온 옛 명령(seq <=)은 버림 ---
static void test_stale_seq() {
  TestClock c; RecMotion m; TestSensors s; Config cfg; Robot r(cfg, &m, &c, &s);
  feed(r, "CMD|HELLO|A|boot1|0|$"); r.tick(true); feed(r, "CMD|RESET|A|5|$");
  feed(r, "CMD|MOVE|A|4|30|0|$");  // seq 4 <= 5 → 버림
  CHECK(m.moves == 0);
  feed(r, "CMD|MOVE|A|6|30|0|$");
  CHECK(m.moves == 1);
}

// --- ESTOP: seq 무관 실행, RESET 전까지 다른 사유로 안 덮임 ---
static void test_estop_priority() {
  TestClock c; RecMotion m; TestSensors s; Config cfg; Robot r(cfg, &m, &c, &s);
  feed(r, "CMD|HELLO|A|boot1|0|$"); r.tick(true); feed(r, "CMD|RESET|A|1|$");
  feed(r, "CMD|MOVE|A|2|40|0|$");
  feed(r, "CMD|ESTOP|A|1|$");       // 낮은 seq 라도 실행
  CHECK(tel_has(r, "|stopped|1|estop|"));
  c.advance(5000); r.tick(false);   // Wi-Fi 끊김 → link_lost 가 되려 해도 estop 유지
  CHECK(tel_has(r, "|estop|"));
}

// --- 잘못된 명령 → 정지 + bad_cmd 래치 ---
static void test_bad_cmd() {
  TestClock c; RecMotion m; TestSensors s; Config cfg; Robot r(cfg, &m, &c, &s);
  feed(r, "CMD|HELLO|A|boot1|0|$"); r.tick(true); feed(r, "CMD|RESET|A|1|$");
  feed(r, "CMD|MOVE|A|2|12.5|0|$");  // 정수 아님 → BAD
  CHECK(tel_has(r, "|stopped|1|bad_cmd|"));
}

// --- 다른 로봇 것은 조용히 버림(래치 없음) ---
static void test_other_robot() {
  TestClock c; RecMotion m; TestSensors s; Config cfg; Robot r(cfg, &m, &c, &s);
  feed(r, "CMD|HELLO|A|boot1|0|$"); r.tick(true); feed(r, "CMD|RESET|A|1|$");
  feed(r, "CMD|MOVE|B|9|40|0|$");   // B 용 → OTHER
  CHECK(m.moves == 0);
  CHECK(tel_has(r, "|idle|0|none|"));  // 래치 안 걸림
}

// --- 통신 끊김: 600ms 명령 없음 → link_lost ---
static void test_link_timeout() {
  TestClock c; RecMotion m; TestSensors s; Config cfg; Robot r(cfg, &m, &c, &s);
  feed(r, "CMD|HELLO|A|boot1|0|$"); r.tick(true); feed(r, "CMD|RESET|A|1|$");
  feed(r, "CMD|MOVE|A|2|40|0|$");
  c.advance(700); r.tick(true);
  CHECK(tel_has(r, "|stopped|1|link_lost|"));
}

// --- 이동 유효시간: MOVE 끊기면 걷기 멈춤(래치 없음) ---
static void test_move_stale() {
  TestClock c; RecMotion m; TestSensors s; Config cfg; Robot r(cfg, &m, &c, &s);
  feed(r, "CMD|HELLO|A|boot1|0|$"); r.tick(true); feed(r, "CMD|RESET|A|1|$");
  feed(r, "CMD|MOVE|A|2|40|0|$");
  c.advance(300); feed(r, "CMD|PING|A|3|$");  // PING 으로 감시는 갱신, MOVE 는 아님
  c.advance(400); r.tick(true);               // 마지막 MOVE 로부터 700ms
  CHECK(m.stops >= 1);
  CHECK(tel_has(r, "move_stale"));
  CHECK(tel_has(r, "|idle|0|none|"));  // 멈추되 래치는 아님
}

// --- 저전압: 2초 연속 미만 → low_battery 래치 ---
static void test_low_battery() {
  TestClock c; RecMotion m; TestSensors s; Config cfg; Robot r(cfg, &m, &c, &s);
  s.batt = 6000;                 // LOW_BATT_LATCH_MV(6600) 미만
  r.tick(true);                  // batt_low_since = now
  c.advance(2100); r.tick(true);
  CHECK(tel_has(r, "low_battery"));
}

// --- 배터리 모름: 3초 연속 → low_battery 래치 ---
static void test_battery_unknown() {
  TestClock c; RecMotion m; TestSensors s; Config cfg; Robot r(cfg, &m, &c, &s);
  s.batt_known = false;
  r.tick(true);
  c.advance(3100); r.tick(true);
  CHECK(tel_has(r, "low_battery"));
  CHECK(tel_has(r, "batt_unknown"));
}

// --- RESET 거부: 배터리 부족하면 해제 안 됨 ---
static void test_reset_denied_low_batt() {
  TestClock c; RecMotion m; TestSensors s; Config cfg; Robot r(cfg, &m, &c, &s);
  s.batt = 6700;                 // LOW_BATT_RESET_MV(6800) 미만
  feed(r, "CMD|HELLO|A|boot1|0|$"); r.tick(true);
  feed(r, "CMD|RESET|A|1|$");
  CHECK(tel_has(r, "reset_denied"));
  CHECK(tel_has(r, "|1|"));      // 아직 래치
}

// --- MOVE 범위 밖 값은 잘라서 실행 + clipped ---
static void test_clipped() {
  TestClock c; RecMotion m; TestSensors s; Config cfg; Robot r(cfg, &m, &c, &s);
  feed(r, "CMD|HELLO|A|boot1|0|$"); r.tick(true); feed(r, "CMD|RESET|A|1|$");
  feed(r, "CMD|MOVE|A|2|999|-99|$");
  CHECK(m.last_step == 100 && m.last_angle == -30);
  CHECK(tel_has(r, "clipped"));
}

// --- 동작 그룹: busy 동안 MOVE 거부, 끝나면 해제 ---
static void test_action_busy() {
  TestClock c; RecMotion m; TestSensors s; Config cfg; Robot r(cfg, &m, &c, &s);
  feed(r, "CMD|HELLO|A|boot1|0|$"); r.tick(true); feed(r, "CMD|RESET|A|1|$");
  m.over = false;                       // 동작 아직 안 끝남
  feed(r, "CMD|ACTION|A|2|sit_dowm|$");
  CHECK(m.actions == 1 && strcmp(m.last_action, "sit_dowm") == 0);
  CHECK(tel_has(r, "|action|"));
  feed(r, "CMD|MOVE|A|3|40|0|$");       // busy → 거부
  CHECK(m.moves == 0);
  CHECK(tel_has(r, "busy"));
  m.over = true;                        // 완료 확인
  c.advance(300); r.tick(true);         // ACTION_MIN_MS 지나 action_over 신뢰
  CHECK(tel_has(r, "|idle|0|none|"));
}

// --- POSE default: set_default_pose 호출 ---
static void test_pose_default() {
  TestClock c; RecMotion m; TestSensors s; Config cfg; Robot r(cfg, &m, &c, &s);
  feed(r, "CMD|HELLO|A|boot1|0|$"); r.tick(true); feed(r, "CMD|RESET|A|1|$");
  feed(r, "CMD|POSE|A|2|default|$");
  CHECK(m.default_poses == 1);
}

// --- 전체 정지(*) ESTOP 허용, 다른 명령에 * 는 BAD ---
static void test_broadcast() {
  TestClock c; RecMotion m; TestSensors s; Config cfg; Robot r(cfg, &m, &c, &s);
  feed(r, "CMD|HELLO|A|boot1|0|$"); r.tick(true); feed(r, "CMD|RESET|A|1|$");
  feed(r, "CMD|ESTOP|*|9|$");
  CHECK(tel_has(r, "|estop|"));
  // * 로 MOVE → BAD 래치
  TestClock c2; RecMotion m2; TestSensors s2; Config cfg2; Robot r2(cfg2, &m2, &c2, &s2);
  feed(r2, "CMD|HELLO|A|boot1|0|$"); r2.tick(true); feed(r2, "CMD|RESET|A|1|$");
  feed(r2, "CMD|MOVE|*|2|40|0|$");
  CHECK(tel_has(r2, "bad_cmd"));
}

int main() {
  test_boot_latched();
  test_before_boot_id();
  test_hello_reset_move();
  test_stale_seq();
  test_estop_priority();
  test_bad_cmd();
  test_other_robot();
  test_link_timeout();
  test_move_stale();
  test_low_battery();
  test_battery_unknown();
  test_reset_denied_low_batt();
  test_clipped();
  test_action_busy();
  test_pose_default();
  test_broadcast();
  printf("\n%d/%d checks passed\n", g_total - g_fail, g_total);
  return g_fail == 0 ? 0 : 1;
}
