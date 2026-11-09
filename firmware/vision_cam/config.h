#pragma once
// 비전 모듈(ESP32-S3 카메라) 맞춤 펌웨어 설정.
// 로봇마다 다른 값(로봇 ID, Wi-Fi)은 커밋하지 않는 secrets.h 에서 덮어씁니다.

#if __has_include("secrets.h")
#include "secrets.h"
#define CAM_HAS_SECRETS 1
#else
#include "secrets.example.h"
#define CAM_HAS_SECRETS 0
#endif

#define CAM_FW_VERSION "0.1.4"

// ── 로봇 ID: "A" 또는 "B". mDNS 이름은 mechdog-<소문자 ID>-cam ──
#ifndef CAM_ROBOT_ID
#define CAM_ROBOT_ID "A"
#endif

// ── Wi-Fi ──
#ifndef CAM_WIFI_SSID
#define CAM_WIFI_SSID ""
#endif
#ifndef CAM_WIFI_PASSWORD
#define CAM_WIFI_PASSWORD ""
#endif
// STA 접속이 이 시간 동안 안 되면 설정·점검용 AP를 켭니다(STA 재시도는 계속).
#define CAM_STA_FALLBACK_MS 30000
#define CAM_STA_RETRY_MS 15000
#define CAM_STA_RETRY_AP_BUSY_MS 60000  // 점검용 AP에 접속자가 있을 때
// 네트워크가 이 시간 동안 전혀 없으면(STA 끊김 + AP 접속자 없음) 재부팅합니다.
#define CAM_NET_RESTART_MS (10UL * 60UL * 1000UL)
// AP 비밀번호가 8자 미만이면 AP를 켜지 않습니다(열린 AP로 영상이 새지 않게).
#ifndef CAM_AP_PASSWORD
#define CAM_AP_PASSWORD ""
#endif
// 고정 IP(선택). 비워 두면 DHCP. 공유기에서 DHCP 예약을 쓰는 것을 권장합니다.
#ifndef CAM_STATIC_IP
#define CAM_STATIC_IP ""
#define CAM_STATIC_GATEWAY ""
#define CAM_STATIC_NETMASK "255.255.255.0"
#endif

// ── 접근 키(선택). 비어 있지 않으면 모든 HTTP 요청에 ?key=<값> 이 있어야 합니다. ──
#ifndef CAM_ACCESS_KEY
#define CAM_ACCESS_KEY ""
#endif

// ── 영상 기본값 ──
// 모델 입력용 시작값입니다. 실측 성능 보장이 아니며 두 대 동시 측정으로 조정합니다.
// 제조사 예제 품질 16보다 압축을 줄이고, 무제한 FPS 대신 수신·추론 여유를 둡니다.
#ifndef CAM_VIDEO_PROFILE
#define CAM_VIDEO_PROFILE 1
#endif
#if CAM_VIDEO_PROFILE == 1
#define CAM_PROFILE_NAME "balanced"
#define CAM_FRAME_SIZE FRAMESIZE_VGA  // 640x480
#define CAM_JPEG_QUALITY 10
#define CAM_TARGET_FPS 15
#elif CAM_VIDEO_PROFILE == 2
#define CAM_PROFILE_NAME "detail"
#define CAM_FRAME_SIZE FRAMESIZE_SVGA  // 800x600, 먼 사람 윤곽 확인용
#define CAM_JPEG_QUALITY 10
#define CAM_TARGET_FPS 10
#else
#error "CAM_VIDEO_PROFILE must be 1 (balanced) or 2 (detail)"
#endif
#define CAM_FB_COUNT 2             // PSRAM 프레임 버퍼 수(최신 프레임 모드)
#define CAM_XCLK_HZ 15000000       // 제조사 예제와 같은 15MHz
// 영상 방향: -1 이면 센서별 기본(OV2640·OV3660·GC032A 상하 반전), 0/1 이면 강제
#define CAM_VFLIP -1
#define CAM_HMIRROR -1

// 아무도 영상을 받지 않으면 이 시간 뒤 촬영을 쉬어 발열을 줄입니다.
#define CAM_IDLE_MS 10000
// 연속 촬영 실패가 이만큼이면 카메라를 다시 초기화, 재초기화가 연속 실패하면 재부팅
#define CAM_FAILS_BEFORE_REINIT 10
#define CAM_REINITS_BEFORE_RESTART 3

// ── HTTP ──
#define CAM_HTTP_PORT 80           // /, /capture, /status
#define CAM_STREAM_PORT 81         // /stream (제조사 기본 펌웨어와 같은 포트)
#define CAM_MAX_STREAM_CLIENTS 2   // Pi 5 한 개 + 점검용 브라우저 한 개
#define CAM_FRAME_WAIT_MS 3000     // 새 프레임을 이 시간 넘게 못 받으면 스트림을 끊음
#define CAM_CAPTURE_WAIT_MS 1500   // /capture 는 짧게 기다리고 503(:80 서버가 오래 막히지 않게)

// ── I2C 슬레이브(메인 보드 공식 ESP32S3Cam 호환) ──
// 0x53: 메인 보드 공식 라이브러리의 레지스터형 읽기(얼굴 0xB0, 색 0xC5 등)를 쓰는 주소.
// 0x52: 제조사 기능별 카메라 펌웨어의 명령형 읽기 주소. 두 형식 모두 응답하므로 주소만 고르면 됩니다.
#ifndef CAM_I2C_ADDR
#define CAM_I2C_ADDR 0x53
#endif
#define CAM_I2C_SDA 47
#define CAM_I2C_SCL 48
#define CAM_I2C_HZ 100000

// ── 워치독 ──
#define CAM_WDT_TIMEOUT_MS 10000
