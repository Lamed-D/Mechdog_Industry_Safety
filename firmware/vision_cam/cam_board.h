#pragma once
// 카메라 연결 핀. 제조사 비전 모듈 예제가 모두 고른 보드 정의(ESP32-S3-EYE 배치)와 같고,
// 제조사 기본 영상 펌웨어에도 같은 카메라 모듈 이름이 들어 있습니다(docs/vision-cam-firmware.md 3절).
#define CAM_PIN_PWDN -1
#define CAM_PIN_RESET -1
#define CAM_PIN_XCLK 15
#define CAM_PIN_SIOD 4
#define CAM_PIN_SIOC 5
#define CAM_PIN_D0 11  // Y2
#define CAM_PIN_D1 9   // Y3
#define CAM_PIN_D2 8   // Y4
#define CAM_PIN_D3 10  // Y5
#define CAM_PIN_D4 12  // Y6
#define CAM_PIN_D5 18  // Y7
#define CAM_PIN_D6 17  // Y8
#define CAM_PIN_D7 16  // Y9
#define CAM_PIN_VSYNC 6
#define CAM_PIN_HREF 7
#define CAM_PIN_PCLK 13
