#include "mech_roles.h"

namespace mech {

bool RoleLease::grant(long new_term, char new_code, long lease_ms) {
  if (new_term < term || (new_term == term && code != ROLE_NONE && code != new_code))
    return false;
  term = new_term;
  code = new_code;
  armed = true;
  if (new_code != ROLE_NONE) {
    has_deadline_ = true;
    deadline_ = ticks_add(clock_->ticks_ms(), (uint32_t)lease_ms);
  } else {
    has_deadline_ = false;
  }
  return true;
}

long RoleLease::remaining() const {
  if (!has_deadline_) return 0;
  int32_t left = ticks_diff(deadline_, clock_->ticks_ms());
  return left > 0 ? left : 0;
}

bool RoleLease::expire() {
  if (code != ROLE_NONE && remaining() == 0) {
    code = ROLE_NONE;
    has_deadline_ = false;
    return true;
  }
  return false;
}

}  // namespace mech
