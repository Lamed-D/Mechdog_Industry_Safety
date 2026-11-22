#pragma once
#include <stdint.h>

// 장치별 설정(로봇 ID, Wi-Fi, AP 비밀번호, 접근 키).
// 우선순위: USB 시리얼로 저장한 값(NVS) > secrets.h 값 > 빈 값.
// 저장소에 올린 미리 빌드한 bin 은 secrets.h 없이 빌드되므로 시리얼 설정만으로 씁니다.
void settings_begin();
void settings_poll_serial();  // loop()에서 호출. 한 줄 명령 처리
const char *settings_robot();     // "A" 또는 "B"
const char *settings_ssid();
const char *settings_password();
const char *settings_ap_password();
const char *settings_key();
