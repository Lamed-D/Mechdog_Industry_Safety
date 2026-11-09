#pragma once
#include <stdint.h>

// 메인 보드가 I2C로 읽는 명령(레지스터)별 응답 표.
// 이 펌웨어는 카메라에서 인식을 하지 않으므로(인식은 Pi 5) 모든 인식 명령에 규격대로 "결과 없음"을 돌려줍니다.
// tests/robot/test_vision_cam_i2c.py 가 이 표를 읽어 docs/protocol.md 11절과 맞는지 검사합니다.
// 형식: { 시작 명령, 끝 명령, 응답 길이, 첫 바이트, 나머지 바이트 }

struct CamI2cRow {
  uint8_t lo;
  uint8_t hi;
  uint8_t len;
  uint8_t first;
  uint8_t rest;
};

static const CamI2cRow CAM_I2C_TABLE[] = {
    {0x00, 0x03, 4, 0x00, 0x00},  // 명령형 읽기(얼굴·색): x,y,w,h 모두 0 = 결과 없음
    {0xA0, 0xAB, 7, 0xFF, 0x00},  // 라인 추적(위/아래): 첫 바이트 0xFF = 인식한 색 없음
    {0xB0, 0xB0, 2, 0x00, 0x00},  // 얼굴 중심 x,y 둘 다 0 = 얼굴 없음
    {0xC5, 0xC5, 7, 0xFF, 0xFF},  // 색 인식: 칸 값이 자기 번호면 인식, 0xFF = 없음(0xC0+5 와 겹치므로 먼저 둠)
    {0xC0, 0xC4, 7, 0xFF, 0x00},  // 색 추적: 첫 바이트 0xFF = 없음
};

#define CAM_I2C_STATUS_CMD 0xE0  // 우리 확장: 상태 4바이트
#define CAM_I2C_STATUS_MAGIC 0x4D  // 'M'
#define CAM_I2C_DEFAULT_LEN 4      // 표에 없는 명령: 0x00 네 개(어떤 형식으로 읽어도 "결과 없음")
#define CAM_I2C_MAX_LEN 8

// 상태 바이트 2의 비트
#define CAM_FLAG_CAMERA_OK 0x01
#define CAM_FLAG_STA 0x02
#define CAM_FLAG_AP 0x04
#define CAM_FLAG_STREAMING 0x08
#define CAM_FLAG_RECOGNITION 0x80  // 카메라 자체 인식 제공 여부(이 펌웨어는 항상 0)

// cmd 에 대한 응답을 out 에 채우고 길이를 돌려줍니다. 상태 명령은 호출한 쪽이 따로 채웁니다.
static inline uint8_t cam_i2c_fill(uint8_t cmd, uint8_t *out) {
  for (unsigned i = 0; i < sizeof(CAM_I2C_TABLE) / sizeof(CAM_I2C_TABLE[0]); i++) {
    const CamI2cRow &row = CAM_I2C_TABLE[i];
    if (cmd >= row.lo && cmd <= row.hi) {
      out[0] = row.first;
      for (uint8_t k = 1; k < row.len; k++) out[k] = row.rest;
      return row.len;
    }
  }
  for (uint8_t k = 0; k < CAM_I2C_DEFAULT_LEN; k++) out[k] = 0x00;
  return CAM_I2C_DEFAULT_LEN;
}
