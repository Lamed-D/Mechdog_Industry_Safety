// 시계 추상화. MicroPython 의 time.ticks_ms/ticks_diff/ticks_add 와 같은 래핑 산술을 씁니다.
// 코어(안전 로직)가 Arduino 에 의존하지 않도록 Clock 을 주입받습니다. 실제 구현은 arduino_clock.h.
#ifndef MECH_CLOCK_H
#define MECH_CLOCK_H
#include <stdint.h>

namespace mech {

class Clock {
 public:
  virtual ~Clock() {}
  virtual uint32_t ticks_ms() = 0;
};

// 래핑(32비트 넘침)을 견디는 차 a-b. 부호 있는 결과.
inline int32_t ticks_diff(uint32_t a, uint32_t b) { return (int32_t)(a - b); }
inline uint32_t ticks_add(uint32_t a, uint32_t ms) { return a + ms; }

}  // namespace mech
#endif
