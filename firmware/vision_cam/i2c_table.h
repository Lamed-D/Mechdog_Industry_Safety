#pragma once
#include <stdint.h>

// 메인 보드가 I2C로 읽을 때 돌려주는 응답.
// 이 펌웨어는 카메라에서 인식을 하지 않으므로(인식은 Pi 5) 어떤 명령에도 "결과 없음"만 돌려줍니다.
//
// 명령과 상관없이 같은 바이트를 보내는 이유: 메인 보드가 명령을 쓰고 STOP 없이 바로 읽으면(반복 시작)
// 코어가 읽기 요청을 명령 수신보다 먼저 알려 줄 수 있어, 직전 명령 기준으로 답하게 됩니다.
// 응답이 명령에 따라 다르면 직전 명령의 응답이 "인식됨"으로 읽힐 수 있으므로 하나로 고정합니다.
// 읽기가 끝나면 코어가 남은 송신 바이트를 비우므로, 요청보다 길게 넣어도 다음 읽기로 넘어가지 않습니다.
// tests/robot/test_vision_cam_i2c.py 가 이 값을 docs/protocol.md 11.2절의 모든 읽기 형식으로 해석해 검사합니다.

#define CAM_I2C_REPLY_LEN 7

// 0x53(메인 보드 공식 라이브러리 레지스터형): 첫 바이트 0xFF, 나머지 0
//   얼굴 중심(x,y)은 둘 다 0이 아니어야 인식 → 0x00 이 있어 없음
//   색 인식은 칸 값이 자기 번호여야 인식 → 0번 칸 0xFF, 나머지 칸 0 이라 없음
//   색·라인 추적은 첫 바이트가 색 번호여야 인식 → 0xFF 라 없음
static const uint8_t CAM_I2C_REPLY_REGISTER[CAM_I2C_REPLY_LEN] = {0xFF, 0, 0, 0, 0, 0, 0};
// 0x52(제조사 기능별 카메라 펌웨어 명령형): x,y,w,h 모두 0 = 결과 없음
static const uint8_t CAM_I2C_REPLY_COMMAND[CAM_I2C_REPLY_LEN] = {0, 0, 0, 0, 0, 0, 0};

static inline const uint8_t *cam_i2c_reply(uint8_t addr) {
  return addr == 0x52 ? CAM_I2C_REPLY_COMMAND : CAM_I2C_REPLY_REGISTER;
}

// 상태 표시용 비트(/status 에서는 쓰지 않음, 시리얼 로그용)
#define CAM_FLAG_CAMERA_OK 0x01
#define CAM_FLAG_STA 0x02
#define CAM_FLAG_AP 0x04
#define CAM_FLAG_STREAMING 0x08
