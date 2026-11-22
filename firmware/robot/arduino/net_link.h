// Wi-Fi STA 접속과 명령·텔레메트리 UDP (ai/protocol.md 1·6절, python/comm.py 이식).
// 통신 전용 예외(ai/mechdog-api.md 9절): 메시지 주고받기에만 쓰고 로봇을 움직이지 않습니다. (Arduino 전용)
#ifndef NET_LINK_H
#define NET_LINK_H
#include <Arduino.h>
#include <WiFi.h>
#include <WiFiUdp.h>
#include "mech_config.h"
#include "mech_clock.h"

class NetLink {
 public:
  NetLink(const mech::Config& cfg, mech::Clock* clock, const char* ssid, const char* pass)
      : cfg_(cfg), clock_(clock), ssid_(ssid), pass_(pass) {}

  void begin();
  void service();        // 접속 상태를 보고 UDP 소켓을 열거나 닫고, 끊겼으면 간격을 두고 재접속
  bool connected();
  bool pm_on() const { return pm_on_; }

  // 받은 데이터그램 하나. 없으면 -1. src_ip 는 보낸 쪽 IP(호스트 바이트, IPAddress 호환).
  int recv(uint8_t* buf, size_t cap, uint32_t& src_ip);
  bool send(const char* line, size_t len, uint32_t ip, uint16_t port);

 private:
  void try_connect();

  const mech::Config& cfg_;
  mech::Clock* clock_;
  const char* ssid_;
  const char* pass_;
  WiFiUDP udp_;
  bool udp_open_ = false;
  bool pm_on_ = false;
  uint32_t last_try_ = 0;
};

#endif
