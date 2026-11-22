#include "lidar_relay.h"

void LidarRelay::begin() {
  uart_.setRxBufferSize(cfg_.LIDAR_RXBUF);
  uart_.begin(cfg_.LIDAR_BAUD, SERIAL_8N1, cfg_.LIDAR_RX_PIN, cfg_.LIDAR_TX_PIN);
  uart_ok_ = true;  // ESP32 HardwareSerial.begin 은 실패를 반환하지 않음. 열림으로 봄.
}

bool LidarRelay::backlogged() {
  if (!has_client_) return false;
  if ((long)waiting_ * 4 >= (long)cfg_.LIDAR_RXBUF * 3) return true;
  if (pending_since_has_ &&
      mech::ticks_diff(clock_->ticks_ms(), pending_since_) >= (int32_t)cfg_.LIDAR_PENDING_WARN_MS)
    return true;
  return false;
}

void LidarRelay::service(bool network_up) {
  if (!network_up) { stop(); return; }
  if (server_ == nullptr) open_server();
  accept_conn();
  if (!has_client_) { drain(); return; }
  waiting_ = uart_.available();
  to_host();
  if (has_client_) to_lidar();
}

void LidarRelay::open_server() {
  server_ = new WiFiServer(cfg_.LIDAR_TCP_PORT);
  server_->begin();
  server_->setNoDelay(true);
}

void LidarRelay::accept_conn() {
  if (server_ == nullptr) return;
  WiFiClient c = server_->accept();
  if (!c) return;
  if (!uart_ok_) { c.stop(); return; }  // UART 를 못 열었으면 받자마자 닫음
  drop();  // 한 번에 하나: 새 연결이 옛 연결을 대신함
  client_ = c;
  has_client_ = true;
  drain();  // 연결 전에 쌓인 오래된 바이트는 보내지 않음
}

void LidarRelay::drop() {
  if (has_client_) { client_.stop(); has_client_ = false; }
  pend_len_ = pend_off_ = 0;
  tx_len_ = tx_off_ = 0;
  pending_since_has_ = false;
  waiting_ = 0;
}

void LidarRelay::drain() {
  if (!uart_ok_) return;
  for (int i = 0; i < 16 && uart_.available(); i++) {
    uint8_t tmp[CHUNK];
    uart_.read(tmp, CHUNK);
  }
}

void LidarRelay::to_host() {
  if (pend_off_ == pend_len_) {  // 보낼 묶음이 비었으면 UART 에서 채움
    pend_len_ = pend_off_ = 0;
    if (waiting_ > 0) {
      size_t want = (size_t)waiting_ < CHUNK ? (size_t)waiting_ : CHUNK;
      int n = uart_.read(pend_, want);
      if (n > 0) {
        pend_len_ = (size_t)n;
        pending_since_ = clock_->ticks_ms();
        pending_since_has_ = true;
      }
    }
  }
  if (pend_off_ == pend_len_) return;
  if (!client_.connected()) { drop(); return; }
  size_t can = client_.availableForWrite();
  if (can == 0) return;  // 밀리면 다음에 (UART 는 그동안 버퍼에 쌓임)
  size_t left = pend_len_ - pend_off_;
  size_t tosend = can < left ? can : left;
  size_t w = client_.write(pend_ + pend_off_, tosend);
  pend_off_ += w;
  if (pend_off_ == pend_len_) {
    pend_len_ = pend_off_ = 0;
    pending_since_has_ = false;
  }
}

void LidarRelay::to_lidar() {
  // 못 쓴 바이트를 먼저 다 쓴 뒤에만 다음 TCP 데이터를 읽음(명령 경계 유지)
  if (tx_off_ == tx_len_) {
    tx_len_ = tx_off_ = 0;
    if (!client_.connected()) { drop(); return; }
    int n = client_.available();
    if (n <= 0) return;
    size_t want = (size_t)n < RECV ? (size_t)n : RECV;
    int r = client_.read(txpend_, want);
    if (r <= 0) return;
    tx_len_ = (size_t)r;
  }
  size_t w = uart_.write(txpend_ + tx_off_, tx_len_ - tx_off_);
  tx_off_ += w;
  if (tx_off_ == tx_len_) tx_len_ = tx_off_ = 0;
}

void LidarRelay::stop() {
  drop();
  if (server_ != nullptr) {
    server_->stop();
    delete server_;
    server_ = nullptr;
  }
}
