#include "net_link.h"

void NetLink::begin() {
  WiFi.mode(WIFI_STA);
  WiFi.persistent(false);
  // 절전 끄기(지연 줄이기). 끄지 못하면 pm_on=true 로 알림(ai/protocol.md 6.1절).
  pm_on_ = !WiFi.setSleep(false);
  try_connect();
}

void NetLink::try_connect() {
  last_try_ = clock_->ticks_ms();
  if (ssid_ == nullptr || ssid_[0] == 0) return;  // secrets 없음: 접속하지 않음(로봇은 래치 유지)
  WiFi.begin(ssid_, pass_);
}

bool NetLink::connected() { return WiFi.status() == WL_CONNECTED; }

void NetLink::service() {
  if (connected()) {
    if (!udp_open_) { udp_.begin(cfg_.CMD_PORT); udp_open_ = true; }
    return;
  }
  if (udp_open_) { udp_.stop(); udp_open_ = false; }
  if ((uint32_t)mech::ticks_diff(clock_->ticks_ms(), last_try_) >= cfg_.WIFI_RETRY_MS) {
    WiFi.disconnect();
    try_connect();
  }
}

int NetLink::recv(uint8_t* buf, size_t cap, uint32_t& src_ip) {
  if (!udp_open_) return -1;
  int n = udp_.parsePacket();
  if (n <= 0) return -1;
  src_ip = (uint32_t)udp_.remoteIP();
  int len = udp_.read(buf, (size_t)n < cap ? (size_t)n : cap);
  return len;
}

bool NetLink::send(const char* line, size_t len, uint32_t ip, uint16_t port) {
  if (!udp_open_ || ip == 0) return false;
  if (udp_.beginPacket(IPAddress(ip), port) != 1) return false;
  udp_.write((const uint8_t*)line, len);
  return udp_.endPacket() == 1;
}
