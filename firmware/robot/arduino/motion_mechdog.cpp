#include "motion_mechdog.h"
#include <math.h>

// 기울기(IMU) 읽기는 read_angle() + radian*_last 전역을 씁니다. 초기화·축 방향을 실물에서 확인하기 전에는
// 기본으로 "모름(false)"을 돌려줍니다(ai/protocol.md 6절: imu_unknown 은 안전한 쪽). 확인 후 아래 매크로로 켭니다.
// #define MECH_ENABLE_IMU 1

void MechDogHw::begin() {
  mechdog_.MechDog_init();
  action_sem_ = xSemaphoreCreateBinary();
  xTaskCreatePinnedToCore(worker_trampoline, "mechAction", 4096, this, 1, &worker_, APP_CPU_NUM);
  mechdog_.move(0, 0);  // 시작은 정지
}

void MechDogHw::action(const char* name) {
  portENTER_CRITICAL(&mux_);
  strncpy(pending_action_, name, sizeof(pending_action_) - 1);
  pending_action_[sizeof(pending_action_) - 1] = 0;
  portEXIT_CRITICAL(&mux_);
  worker_busy_ = true;  // action_over()가 바로 false 를 돌려주도록 시작 전에 올림
  if (action_sem_) xSemaphoreGive(action_sem_);
}

void MechDogHw::worker_loop() {
  for (;;) {
    xSemaphoreTake(action_sem_, portMAX_DELAY);
    char name[20];
    portENTER_CRITICAL(&mux_);
    strncpy(name, pending_action_, sizeof(name) - 1);
    portEXIT_CRITICAL(&mux_);
    name[sizeof(name) - 1] = 0;
    mechdog_.action_run(name);  // 동작 그룹이 끝날 때까지 블로킹(벤더 구현)
    worker_busy_ = false;
  }
}

bool MechDogHw::read_battery(int32_t& mv) {
  // 벤더 readBattery(). 단위(mV 추정)·실패값은 실물 확인 필요(ai/protocol.md 5.4절 [확인 필요]).
  long v = mechdog_.readBattery();
  if (v <= 0) return false;  // 0·음수는 "모름"으로 처리(충분함으로 보지 않음)
  mv = (int32_t)v;
  return true;
}

bool MechDogHw::read_tilt(float& x, float& y) {
#ifdef MECH_ENABLE_IMU
  read_angle();  // radianX_last / radianY_last 갱신 (축 대응 [확인 필요])
  x = radianX_last;
  y = radianY_last;
  return isfinite(x) && isfinite(y);
#else
  (void)x;
  (void)y;
  return false;  // IMU 초기화·축을 확인하기 전에는 imu_unknown (안전)
#endif
}
