#include "i2c_compat.h"

#include <Arduino.h>
#include <Wire.h>

#include "config.h"
#include "i2c_table.h"

static volatile uint32_t s_requests = 0;

// 메인 보드가 쓴 명령 바이트는 읽어서 버리기만 합니다(응답이 명령과 무관, i2c_table.h 참고).
static void on_receive(int len) {
  while (Wire.available()) Wire.read();
}

static void on_request() {
  Wire.write(cam_i2c_reply(CAM_I2C_ADDR), CAM_I2C_REPLY_LEN);
  s_requests = s_requests + 1;
}

bool i2c_compat_begin() {
  Wire.onReceive(on_receive);
  Wire.onRequest(on_request);
  return Wire.begin((uint8_t)CAM_I2C_ADDR, CAM_I2C_SDA, CAM_I2C_SCL, CAM_I2C_HZ);
}

uint32_t i2c_compat_requests() { return s_requests; }
