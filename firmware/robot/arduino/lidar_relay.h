// RPLIDAR 원시 중계: J5 UART <-> TCP (ai/protocol.md 7절, firmware/robot/python/lidar_bridge.py 이식).
// 바이트를 해석·가공하지 않고 같은 순서로 넘깁니다. 로봇을 움직이지 않으며 안전 래치와 무관합니다.
// machine.UART 직접 사용 예외(ai/mechdog-api.md 6절)에 해당. (Arduino 전용)
#ifndef LIDAR_RELAY_H
#define LIDAR_RELAY_H
#include <Arduino.h>
#include <WiFi.h>
#include "mech_config.h"
#include "mech_clock.h"

class LidarRelay {
 public:
  LidarRelay(const mech::Config& cfg, mech::Clock* clock) : cfg_(cfg), clock_(clock), uart_(1) {}

  void begin();            // UART 열기
  bool uart_ok() const { return uart_ok_; }
  bool backlogged();
  void service(bool network_up);  // 짧은 주기로 반복
  void stop();

 private:
  void open_server();
  void accept_conn();
  void drop();
  void drain();
  void to_host();
  void to_lidar();

  const mech::Config& cfg_;
  mech::Clock* clock_;
  HardwareSerial uart_;
  bool uart_ok_ = false;
  WiFiServer* server_ = nullptr;
  WiFiClient client_;
  bool has_client_ = false;

  static const size_t CHUNK = 512;   // UART 에서 한 번에 읽는 최대
  static const size_t RECV = 64;     // 호스트 -> 라이다 명령은 짧음
  uint8_t pend_[CHUNK];              // 라이다 -> 호스트 아직 못 보낸 바이트
  size_t pend_len_ = 0, pend_off_ = 0;
  uint8_t txpend_[RECV];             // 호스트 -> 라이다 아직 못 쓴 바이트
  size_t tx_len_ = 0, tx_off_ = 0;
  bool pending_since_has_ = false;
  uint32_t pending_since_ = 0;
  int waiting_ = 0;
};

#endif
