// 명령 처리·감시·래치·저전압 (ai/protocol.md 4·5·6절). python/core.py 의 Arduino 이식.
// 벤더·Arduino 비의존: 하드웨어는 MotionBackend·Sensors·Clock 주입으로만 만집니다.
// 동시 실행(수신·감시·텔레메트리 태스크)은 상위(.ino)에서 뮤텍스로 직렬화합니다.
#ifndef MECH_CORE_H
#define MECH_CORE_H
#include <stdint.h>
#include <stddef.h>
#include "mech_config.h"
#include "mech_proto.h"
#include "mech_clock.h"
#include "mech_backend.h"
#include "mech_roles.h"

namespace mech {

enum LatchReason { LR_NONE, LR_BOOT, LR_LINK_LOST, LR_ESTOP, LR_LOW_BATTERY, LR_BAD_CMD };

struct OptU { bool has = false; uint32_t v = 0; };
struct OptI { bool has = false; int32_t v = 0; };

class Robot {
 public:
  Robot(const Config& cfg, MotionBackend* motion, Clock* clock, Sensors* sensors);

  // --- 상위 태스크가 뮤텍스 안에서 부릅니다 ---
  void handle(const uint8_t* data, size_t len, uint32_t src_ip);  // 명령 수신 (4절)
  void tick(bool wifi_connected);                                 // 감시 (5절)
  bool telemetry_due();
  size_t telemetry(char* out, size_t cap);     // 다음 TEL 한 줄. 길이 반환(0=없음)
  size_t role_status(char* out, size_t cap);   // ROLE 상태 한 줄. 0=역할 없음
  uint32_t telemetry_dest_ip();                // 0=보낼 곳 모름
  void fail_safe();                            // 예외 경로: 멈추고 link_lost 래치
  void set_condition(Warn w, bool on);         // pm_on·lidar_uart·lidar_backlog
  char robot_id() const { return cfg_.ROBOT_ID; }

 private:
  uint32_t now_() { return clock_->ticks_ms(); }
  int32_t diff_(uint32_t a, uint32_t b) { return ticks_diff(a, b); }
  bool before_(const OptU& d) { return d.has && ticks_diff(d.v, now_()) > 0; }
  void addev_(Warn w) { events_ |= (1u << w); }

  bool busy_();
  const char* state_str_();
  const char* latch_str_();
  void stop_();
  void stop_action_();
  void latch_(LatchReason reason);

  void handle_(ParseKind kind, const Command& cmd, uint32_t src_ip);
  void accept_(long seq);
  void accept_if_newer_(long seq);
  void hello_(const Command& cmd, uint32_t src_ip);
  void reset_();
  void move_(long step, long angle);
  void action_(const char* name);
  void pose_(const char* pose);

  enum Reading { NOT_READ, READ_UNKNOWN, READ_VALUE };
  void tick_(bool wifi_connected, Reading kind, int32_t value);
  void check_action_(uint32_t now);
  void check_battery_(uint32_t now, bool known, int32_t value);

  const Config& cfg_;
  MotionBackend* motion_;
  Clock* clock_;
  Sensors* sensors_;
  RoleLease roles_;

  bool latched_;
  LatchReason latch_reason_;
  bool has_boot_id_;
  char boot_id_[17];
  long last_cmd_seq_;
  bool moving_;
  bool stop_pending_;
  OptU action_until_;
  bool has_action_name_;
  char action_name_[20];
  OptU action_started_;
  OptU action_max_end_;
  OptU reset_block_until_;
  bool need_default_pose_;
  bool link_armed_;
  uint32_t last_accept_;
  uint32_t last_move_;
  bool wifi_ok_;
  OptI battery_mv_;
  OptU batt_low_since_;
  OptU batt_unknown_since_;
  OptU last_batt_read_;
  uint32_t conditions_;  // 비트마스크
  uint32_t events_;      // 비트마스크
  uint32_t tel_addr_;    // 마지막 HELLO 보낸 IP (0=없음)
  long tseq_;
  bool urgent_;
  uint32_t last_tel_;
  uint32_t uptime_ms_;
  uint32_t last_tick_;
};

}  // namespace mech
#endif
