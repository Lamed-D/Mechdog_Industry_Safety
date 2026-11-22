#pragma once
#include <stdint.h>

// 메인 보드(공식 Hiwonder_IIC.ESP32S3Cam)가 붙는 I2C 슬레이브. 늘 "결과 없음"으로 답합니다.
bool i2c_compat_begin();
uint32_t i2c_compat_requests();
