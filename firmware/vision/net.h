#pragma once
#include <stdint.h>

// Wi-Fi: 전용 공유기에 STA로 접속, 실패가 길어지면 점검용 AP를 켬. mDNS 이름 등록.
void net_begin();
void net_loop();  // loop()에서 계속 호출
bool net_sta_connected();
bool net_ap_on();
int net_rssi();             // STA 접속 중일 때만 의미 있음
const char *net_hostname();  // 예: mechdog-a-cam
const char *net_mode();      // "sta", "ap", "sta+ap", "none"
void net_ip(char *out, int cap);
uint32_t net_sta_reconnects();
