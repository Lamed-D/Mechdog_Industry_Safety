// millis() 기반 Clock 구현. 코어에 주입합니다. (Arduino 전용)
#ifndef ARDUINO_CLOCK_H
#define ARDUINO_CLOCK_H
#include <Arduino.h>
#include "mech_clock.h"

class ArduinoClock : public mech::Clock {
 public:
  uint32_t ticks_ms() override { return millis(); }
};

#endif
