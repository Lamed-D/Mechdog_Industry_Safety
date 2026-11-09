#include "i2c_compat.h"

#include <Arduino.h>
#include <Wire.h>

#include "config.h"
#include "i2c_table.h"

static volatile uint8_t s_cmd = 0xFF;
static volatile uint8_t s_flags = 0;
static volatile uint8_t s_clients = 0;
static volatile uint32_t s_requests = 0;

// 메인 보드가 먼저 명령 한 바이트를 쓰고, 이어서 읽습니다. 마지막으로 받은 바이트를 명령으로 씁니다.
static void on_receive(int len) {
  while (Wire.available()) s_cmd = (uint8_t)Wire.read();
}

static void on_request() {
  uint8_t out[CAM_I2C_MAX_LEN];
  uint8_t len;
  uint8_t cmd = s_cmd;
  if (cmd == CAM_I2C_STATUS_CMD) {
    out[0] = CAM_I2C_STATUS_MAGIC;
    out[1] = CAM_FW_VERSION_BYTE;
    out[2] = s_flags;
    out[3] = s_clients;
    len = 4;
  } else {
    len = cam_i2c_fill(cmd, out);
  }
  Wire.write(out, len);
  s_requests = s_requests + 1;
}

bool i2c_compat_begin() {
  Wire.onReceive(on_receive);
  Wire.onRequest(on_request);
  return Wire.begin((uint8_t)CAM_I2C_ADDR, CAM_I2C_SDA, CAM_I2C_SCL, CAM_I2C_HZ);
}

void i2c_compat_set_status(uint8_t flags, uint8_t stream_clients) {
  s_flags = flags;
  s_clients = stream_clients;
}

uint32_t i2c_compat_requests() { return s_requests; }
