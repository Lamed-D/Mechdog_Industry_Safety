// 컴파일 전용 예비 판 골격. 통신·구동 미구현이며 장치에 굽는 배포물이 아닙니다.
// 공식 API의 동작 중단/완료 확인 대응을 검증하기 전 구동 백엔드를 넣지 않습니다.
#include <Arduino.h>
#include "protocol_contract.h"

static bool boot_latched = true;

void setup() {
  Serial.begin(115200);
  Serial.println("main_arduino skeleton: no motion backend, no network, not deployable");
}

void loop() {
  // 역할 배정·RESET 수신도 아직 구현하지 않았으므로 부팅 래치 상태를 유지합니다.
  boot_latched = true;
  delay(mechdog_contract::WATCHDOG_PERIOD_MS);
}
