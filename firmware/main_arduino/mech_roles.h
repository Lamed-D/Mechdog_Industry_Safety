// 같은 장비의 A/B 식별자와 별개인 임대 역할. robot/roles.py 의 Arduino 이식.
// 제어 권한·래치 해제를 만들지 않습니다(docs/robot-redundancy.md).
#ifndef MECH_ROLES_H
#define MECH_ROLES_H
#include <stdint.h>
#include "mech_clock.h"
#include "mech_proto.h"

namespace mech {

class RoleLease {
 public:
  long term = 0;
  char code = ROLE_NONE;
  bool armed = false;

  explicit RoleLease(Clock* clock) : clock_(clock) {}

  // 같은/높은 term 이고 code 충돌이 없을 때만 받아들입니다.
  bool grant(long new_term, char new_code, long lease_ms);
  long remaining() const;
  bool expire();

 private:
  Clock* clock_;
  bool has_deadline_ = false;
  uint32_t deadline_ = 0;
};

}  // namespace mech
#endif
