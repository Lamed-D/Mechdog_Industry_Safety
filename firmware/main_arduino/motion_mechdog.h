// 제조사 공식 MechDog Arduino 라이브러리(HW_MechDog) 로 코어의 MotionBackend·Sensors 를 구현합니다.
// 공식 동작 함수(move·set_default_pose·action_run·readBattery·read_angle)만 쓰고, 서보를 직접 구동하지 않습니다.
// 이 파일만 벤더 헤더를 포함합니다. 벤더 라이브러리는 저장소에 넣지 않고 사용자가 제조사 패키지로 설치합니다
// (docs/firmware-strategy.md, firmware/main_arduino/README.md). (Arduino 전용, 컴파일 검증만)
//
// 핵심: 벤더 action_run() 은 끝까지 블로킹합니다. 수신·감시 태스크를 막지 않도록 전용 워커 태스크에서 돌립니다.
//   중단(stop_action) API 는 라이브러리에 없으므로 동작 그룹은 실행 중 멈출 수 없습니다(docs/protocol.md 3.3절).
#ifndef MOTION_MECHDOG_H
#define MOTION_MECHDOG_H
#include <Arduino.h>
#include "mech_base_types.h"
#include "HW_MechDog.h"
#include "mech_backend.h"

class MechDogHw : public mech::MotionBackend, public mech::Sensors {
 public:
  void begin();  // MechDog_init + 워커 태스크 생성 + 초기 정지. setup()에서 한 번.

  // MotionBackend
  void stop() override { mechdog_.move(0, 0); }
  void move(long step, long angle) override { mechdog_.move((float)step, (float)angle); }
  void action(const char* name) override;
  void stop_action() override {}  // 벤더에 중단 API 없음: no-op (docs/protocol.md 3.3절 [확인 필요])
  bool action_over() override { return !worker_busy_; }
  void default_pose() override { mechdog_.set_default_pose(); }

  // Sensors
  bool read_battery(int32_t& mv) override;
  bool read_tilt(float& x, float& y) override;

 private:
  static void worker_trampoline(void* self) { static_cast<MechDogHw*>(self)->worker_loop(); }
  void worker_loop();

  MechDog mechdog_;
  TaskHandle_t worker_ = nullptr;
  SemaphoreHandle_t action_sem_ = nullptr;
  volatile bool worker_busy_ = false;
  portMUX_TYPE mux_ = portMUX_INITIALIZER_UNLOCKED;
  char pending_action_[20] = {0};
};

#endif
