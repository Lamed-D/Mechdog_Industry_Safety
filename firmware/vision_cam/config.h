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

#define CAM_FW_VERSION "0.1.0"
#define CAM_FW_VERSION_BYTE 0x01  // I2C 상태 레지스터에 싣는 버전(상위 4비트 major, 하위 4비트 minor)

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
#define CAM_STA_RETRY_MS 10000
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
// VGA(640x480) JPEG 품질 12: 사람·자세 판단에 쓰기 충분하고, 한 장 약 20~40KB로
// 두 대가 같은 공유기를 써도 대역이 남는 크기. 실측 후 docs/vision-cam-firmware.md 에 기록합니다.
#define CAM_FRAME_SIZE FRAMESIZE_VGA
#define CAM_JPEG_QUALITY 12        // 0~63, 낮을수록 고화질·큰 파일
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
