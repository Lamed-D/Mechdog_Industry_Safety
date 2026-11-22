// robot/core.py 의 Arduino 이식. 분기·상태 전이를 Python 판과 1:1 로 맞춥니다.
// 동시 실행 직렬화(뮤텍스)는 상위(.ino)가 책임집니다. 센서 읽기는 짧으므로 tick/telemetry 안에서 합니다.
#include "mech_core.h"
#include <stdio.h>
#include <string.h>

namespace mech {

Robot::Robot(const Config& cfg, MotionBackend* motion, Clock* clock, Sensors* sensors)
    : cfg_(cfg), motion_(motion), clock_(clock), sensors_(sensors), roles_(clock) {
  uint32_t n = clock_->ticks_ms();
  latched_ = true;
  latch_reason_ = LR_BOOT;  // 부팅 직후에는 사람이 RESET 하기 전까지 움직이지 않음 (5.1절)
  has_boot_id_ = false;
  boot_id_[0] = 0;
  last_cmd_seq_ = 0;
  moving_ = false;
  stop_pending_ = false;
  has_action_name_ = false;
  action_name_[0] = 0;
  need_default_pose_ = false;
  link_armed_ = false;
  last_accept_ = n;
  last_move_ = n;
  wifi_ok_ = false;
  batt_unknown_since_.has = true;
  batt_unknown_since_.v = n;
  conditions_ = 0;
  events_ = 0;
  tel_addr_ = 0;
  tseq_ = 0;
  urgent_ = true;  // 부팅 상태를 바로 한 번 알림
  last_tel_ = n;
  uptime_ms_ = 0;
  last_tick_ = n;
}

// ---------- 공용 ----------
bool Robot::busy_() { return has_action_name_ || before_(action_until_); }

const char* Robot::state_str_() {
  if (latched_) return "stopped";
  if (busy_()) return "action";
  if (moving_) return "moving";
  return "idle";
}

const char* Robot::latch_str_() {
  switch (latch_reason_) {
    case LR_NONE: return "none";
    case LR_BOOT: return "boot";
    case LR_LINK_LOST: return "link_lost";
    case LR_ESTOP: return "estop";
    case LR_LOW_BATTERY: return "low_battery";
    case LR_BAD_CMD: return "bad_cmd";
  }
  return "none";
}

void Robot::stop_() {
  stop_pending_ = true;
  motion_->stop();
  moving_ = false;
  stop_pending_ = false;
}

void Robot::stop_action_() {
  motion_->stop_action();  // 없거나 실패해도 아래 stop() 은 반드시 부름(벤더엔 중단 API 없음)
  stop_();
}

void Robot::latch_(LatchReason reason) {
  if (has_action_name_) {
    // 동작 그룹이 끝났다고 확인되지 않았으면 최대 시간까지 RESET 을 막음
    if (action_max_end_.has && before_(action_max_end_)) reset_block_until_ = action_max_end_;
  }
  stop_action_();
  // estop 은 RESET 전까지 다른 사유로 덮지 않음 (5.2절)
  bool skip = (latched_ && latch_reason_ == LR_ESTOP && reason != LR_ESTOP);
  if (!skip) {
    if (!latched_ || latch_reason_ != reason) urgent_ = true;
    latch_reason_ = reason;
  }
  latched_ = true;
}

void Robot::fail_safe() { latch_(LR_LINK_LOST); }

void Robot::set_condition(Warn w, bool on) {
  if (on) conditions_ |= (1u << w);
  else conditions_ &= ~(1u << w);
}

// ---------- 명령 수신 (4절) ----------
void Robot::handle(const uint8_t* data, size_t len, uint32_t src_ip) {
  Command cmd;
  ParseKind kind = parse(data, len, cfg_.ROBOT_ID, cmd);
  handle_(kind, cmd, src_ip);
}

void Robot::handle_(ParseKind kind, const Command& cmd, uint32_t src_ip) {
  if (kind == PK_GARBAGE) { addev_(W_GARBAGE); return; }
  if (kind == PK_OTHER) return;
  if (kind == PK_BAD) { latch_(LR_BAD_CMD); return; }

  CmdName n = cmd.name;
  if (n == CMD_ESTOP) { accept_if_newer_(cmd.seq); latch_(LR_ESTOP); return; }
  if (n == CMD_STOP) { accept_if_newer_(cmd.seq); stop_(); return; }
  if (n == CMD_HELLO) { hello_(cmd, src_ip); return; }
  if (!has_boot_id_) return;  // boot_id 를 모르면 STOP·ESTOP 만 (2.2절)
  if (cmd.seq <= last_cmd_seq_) return;  // 늦게 온 옛 명령

  if (n == CMD_ROLE) {
    char previous = roles_.code;
    if (strcmp(cmd.text, boot_id_) != 0 || !roles_.grant(cmd.a0, cmd.code, cmd.a1)) return;
    accept_(cmd.seq);
    if (previous != ROLE_NONE && previous != cmd.code) latch_(LR_LINK_LOST);  // 역할 변경
    urgent_ = true;
    return;
  }

  accept_(cmd.seq);
  if (latched_ || stop_pending_) {
    if (n == CMD_RESET) reset_();
    else if (n == CMD_MOVE || n == CMD_ACTION || n == CMD_POSE) addev_(W_LATCHED);
    return;
  }
  if (n == CMD_RESET || n == CMD_PING) return;
  if (busy_()) { addev_(W_BUSY); return; }
  if (n == CMD_MOVE) move_(cmd.a0, cmd.a1);
  else if (n == CMD_ACTION) action_(cmd.text);
  else if (n == CMD_POSE) pose_(cmd.text);
}

void Robot::accept_(long seq) {
  last_cmd_seq_ = seq;
  last_accept_ = now_();
  link_armed_ = true;
}

void Robot::accept_if_newer_(long seq) {
  if (has_boot_id_ && seq > last_cmd_seq_) accept_(seq);
}

void Robot::hello_(const Command& cmd, uint32_t src_ip) {
  if (cmd.a0 != PROTO_VERSION) { addev_(W_PROTO); return; }
  if (src_ip != 0) tel_addr_ = src_ip;
  if (moving_ || busy_()) latch_(LR_LINK_LOST);  // 복구 HELLO 가 실행 중 동작의 생존 신호가 되지 않음
  bool different = !has_boot_id_ || strcmp(cmd.text, boot_id_) != 0;
  if (different) {
    if (roles_.armed) {
      latch_(LR_LINK_LOST);
      roles_ = RoleLease(clock_);
    }
    stop_();
    last_cmd_seq_ = 0;
    strncpy(boot_id_, cmd.text, sizeof(boot_id_) - 1);
    boot_id_[sizeof(boot_id_) - 1] = 0;
    has_boot_id_ = true;  // 래치는 그대로 둠
    urgent_ = true;
  }
  last_accept_ = now_();
  link_armed_ = true;
}

void Robot::reset_() {
  bool ok = wifi_ok_ && battery_mv_.has && battery_mv_.v >= cfg_.LOW_BATT_RESET_MV &&
            !stop_pending_ && !busy_() && !before_(reset_block_until_);
  if (!ok) { addev_(W_RESET_DENIED); return; }
  reset_block_until_.has = false;
  latched_ = false;
  latch_reason_ = LR_NONE;
  urgent_ = true;
}

void Robot::move_(long step, long angle) {
  bool c1, c2;
  step = clip(step, -100, 100, c1);
  angle = clip(angle, -30, 30, c2);
  if (c1 || c2) addev_(W_CLIPPED);
  if (step == 0 && angle == 0) { stop_(); return; }
  if (need_default_pose_) {
    // 동작 그룹 뒤 첫 MOVE: 기본 자세를 먼저 잡고, 자세가 잡힌 뒤 오는 MOVE 부터 걷기 (3.3절)
    need_default_pose_ = false;
    motion_->default_pose();
    action_until_.has = true;
    action_until_.v = ticks_add(now_(), cfg_.DEFAULT_POSE_SETTLE_MS);
    addev_(W_BUSY);
    return;
  }
  motion_->move(step, angle);
  moving_ = true;
  last_move_ = now_();
}

void Robot::action_(const char* name) {
  if (moving_) stop_();
  // 공식 호출이 동작을 시작한 뒤 예외를 내도 정지 경로가 추적할 수 있게 먼저 기록합니다.
  has_action_name_ = true;
  strncpy(action_name_, name, sizeof(action_name_) - 1);
  action_name_[sizeof(action_name_) - 1] = 0;
  uint32_t t = now_();
  action_started_.has = true;
  action_started_.v = t;
  action_max_end_.has = true;
  action_max_end_.v = ticks_add(t, cfg_.action_duration_ms(name));
  action_until_ = action_max_end_;
  need_default_pose_ = true;
  motion_->action(name);
}

void Robot::pose_(const char* pose) {
  bool is_default;
  const char* act = pose_to_action(pose, is_default);
  if (act != nullptr) { action_(act); return; }
  stop_();
  motion_->default_pose();
  need_default_pose_ = false;
  action_until_.has = true;
  action_until_.v = ticks_add(now_(), cfg_.DEFAULT_POSE_SETTLE_MS);
}

// ---------- 감시 (5절) ----------
void Robot::tick(bool wifi_connected) {
  uint32_t n = now_();
  Reading kind = NOT_READ;
  int32_t value = 0;
  if (!last_batt_read_.has ||
      diff_(n, last_batt_read_.v) >= (int32_t)cfg_.BATT_READ_PERIOD_MS) {
    int32_t mv;
    if (sensors_->read_battery(mv) && mv > 0) { kind = READ_VALUE; value = mv; }
    else kind = READ_UNKNOWN;  // 모르는 값을 "충분함"으로 보지 않음
  }
  tick_(wifi_connected, kind, value);
}

void Robot::tick_(bool wifi_connected, Reading kind, int32_t value) {
  uint32_t n = now_();
  int32_t d = diff_(n, last_tick_);
  if (d < 0) d = 0;
  uptime_ms_ += (uint32_t)d;
  last_tick_ = n;
  if (stop_pending_) latch_(LR_LINK_LOST);
  if (roles_.expire()) latch_(LR_LINK_LOST);
  check_action_(n);
  if (!wifi_connected && wifi_ok_) latch_(LR_LINK_LOST);
  wifi_ok_ = wifi_connected;
  if (link_armed_ && diff_(n, last_accept_) > (int32_t)cfg_.LINK_TIMEOUT_MS) {
    link_armed_ = false;
    latch_(LR_LINK_LOST);
  }
  if (moving_ && (latched_ || diff_(n, last_move_) > (int32_t)cfg_.MOVE_HOLD_MS)) {
    stop_();
    if (!latched_) addev_(W_MOVE_STALE);
  }
  if (kind != NOT_READ) {
    last_batt_read_.has = true;
    last_batt_read_.v = n;
    check_battery_(n, kind == READ_VALUE, value);
  }
}

void Robot::check_action_(uint32_t n) {
  if (has_action_name_ && diff_(n, action_started_.v) >= (int32_t)cfg_.ACTION_MIN_MS) {
    bool over = motion_->action_over();  // 제조사 run_status 기반 끝남 확인
    if (over) {
      has_action_name_ = false;
      action_started_.has = false;
      action_max_end_.has = false;
      action_until_.has = false;
      return;
    }
  }
  if (action_until_.has && !before_(action_until_)) {
    action_until_.has = false;
    // 최대 시간이 지났는데 끝났다고 확인되지 않음: 멈추게 하고, 확인될 때까지 계속 추적
    if (has_action_name_) stop_action_();
  }
}

void Robot::check_battery_(uint32_t n, bool known, int32_t value) {
  if (!known) {
    battery_mv_.has = false;
    batt_low_since_.has = false;
    if (!batt_unknown_since_.has) { batt_unknown_since_.has = true; batt_unknown_since_.v = n; }
    if (diff_(n, batt_unknown_since_.v) >= (int32_t)cfg_.BATT_UNKNOWN_HOLD_MS) latch_(LR_LOW_BATTERY);
    return;
  }
  battery_mv_.has = true;
  battery_mv_.v = value;
  batt_unknown_since_.has = false;
  if (value < cfg_.LOW_BATT_LATCH_MV) {
    if (!batt_low_since_.has) { batt_low_since_.has = true; batt_low_since_.v = n; }
    if (diff_(n, batt_low_since_.v) >= (int32_t)cfg_.LOW_BATT_HOLD_MS) latch_(LR_LOW_BATTERY);
  } else {
    batt_low_since_.has = false;
  }
}

// ---------- 텔레메트리 (6절) ----------
bool Robot::telemetry_due() {
  return urgent_ || diff_(now_(), last_tel_) >= (int32_t)cfg_.TEL_PERIOD_MS;
}

uint32_t Robot::telemetry_dest_ip() { return tel_addr_; }

size_t Robot::telemetry(char* out, size_t cap) {
  float tx, ty;
  bool tilt_known = sensors_->read_tilt(tx, ty);  // 짧은 I2C 읽기
  uint32_t words = events_ | conditions_;

  char battery[12];
  if (!battery_mv_.has) { words |= (1u << W_BATT_UNKNOWN); strcpy(battery, "NA"); }
  else {
    snprintf(battery, sizeof(battery), "%ld", (long)battery_mv_.v);
    if (battery_mv_.v < cfg_.LOW_BATT_WARN_MV) words |= (1u << W_BATT_LOW);
  }
  char sx[12], sy[12];
  if (!tilt_known) { words |= (1u << W_IMU_UNKNOWN); strcpy(sx, "NA"); strcpy(sy, "NA"); }
  else { snprintf(sx, sizeof(sx), "%.1f", (double)tx); snprintf(sy, sizeof(sy), "%.1f", (double)ty); }

  const char* boot = has_boot_id_ ? boot_id_ : "-";
  char head[140];
  int hn = snprintf(head, sizeof(head), "TEL|%c|%ld|%ld|%s|%d|%s|%s|%s|%s|%lu|%s|",
                    cfg_.ROBOT_ID, tseq_, last_cmd_seq_, state_str_(), latched_ ? 1 : 0,
                    latch_str_(), battery, sx, sy, (unsigned long)uptime_ms_, boot);
  if (hn < 0 || (size_t)hn >= cap) return 0;

  const char* list[WARN_COUNT];
  int nlist = 0;
  for (int i = 0; i < WARN_COUNT; i++)
    if (words & (1u << i)) list[nlist++] = WARN_WORDS[i];
  // 길이 제한: 뒤쪽(덜 급한) 낱말부터 뺌
  while (nlist > 0) {
    int jl = 0;
    for (int i = 0; i < nlist; i++) { jl += (int)strlen(list[i]); if (i) jl += 1; }
    if ((size_t)(hn + jl + 2) > (size_t)MAX_TEL_LEN) nlist--;
    else break;
  }

  int pos = hn;
  memcpy(out, head, hn);
  if (nlist == 0) {
    if ((size_t)(pos + 4) >= cap) return 0;
    memcpy(out + pos, "none", 4); pos += 4;
  } else {
    for (int i = 0; i < nlist; i++) {
      if (i) { if ((size_t)(pos + 1) >= cap) return 0; out[pos++] = ','; }
      int l = (int)strlen(list[i]);
      if ((size_t)(pos + l) >= cap) return 0;
      memcpy(out + pos, list[i], l); pos += l;
    }
  }
  if ((size_t)(pos + 2) >= cap) return 0;
  out[pos++] = '|'; out[pos++] = '$'; out[pos] = 0;

  tseq_++;
  events_ = 0;
  urgent_ = false;
  last_tel_ = now_();
  return (size_t)pos;
}

size_t Robot::role_status(char* out, size_t cap) {
  if (!roles_.armed) return 0;
  const char* boot = has_boot_id_ ? boot_id_ : "-";
  int n = snprintf(out, cap, "ROLE|%c|%s|%ld|%c|%ld|%ld|$", cfg_.ROBOT_ID, boot,
                   roles_.term, roles_.code, roles_.remaining(), tseq_);
  if (n < 0 || (size_t)n >= cap) return 0;
  return (size_t)n;
}

}  // namespace mech
