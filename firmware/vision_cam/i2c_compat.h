#pragma once
#include <stdint.h>

// 메인 보드(공식 Hiwonder_IIC.ESP32S3Cam)가 붙는 I2C 슬레이브.
bool i2c_compat_begin();
// loop()에서 주기적으로 상태를 넘겨 둡니다(요청 처리 중에는 잠금을 쓰지 않기 위해).
void i2c_compat_set_status(uint8_t flags, uint8_t stream_clients);
uint32_t i2c_compat_requests();
