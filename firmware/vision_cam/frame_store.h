#pragma once
#include <stddef.h>
#include <stdint.h>

// 카메라 촬영 작업과 "최신 프레임 한 장" 저장소.
// 촬영 작업이 계속 최신 JPEG 하나만 남기고, 스트림·캡처 요청은 그 사본을 가져갑니다.
// 따라서 느린 수신자가 있어도 오래된 프레임이 쌓이지 않습니다.

struct CamStats {
  bool camera_ok;
  bool psram;
  bool idle;
  uint16_t width;
  uint16_t height;
  uint8_t quality;
  const char *sensor;
  float fps;
  float kbps;           // 저장에 성공한 JPEG 바이트 기준, HTTP 중복 수신자는 별도
  uint32_t frames;
  uint32_t failures;
  uint32_t reinits;
  int64_t last_frame_us;  // 마지막 프레임 촬영 시각(부팅 기준, 0=없음)
  size_t last_len;
};

bool frame_store_begin();           // 카메라 초기화 + 촬영 작업 시작
void frame_store_demand();          // 누군가 영상을 원함(쉬는 중이면 촬영 재개)
// after_seq 보다 새 프레임을 timeout_ms 안에 dst 로 복사. 성공하면 길이, 실패하면 0.
// dst 가 작으면 *need 에 필요한 크기를 알려 주고 0을 돌려줍니다.
size_t frame_store_copy(uint8_t *dst, size_t cap, uint32_t after_seq, uint32_t timeout_ms,
                        uint32_t *seq_out, int64_t *ts_us_out, size_t *need);
uint32_t frame_store_seq();
CamStats frame_store_stats();
