#pragma once
// 이 파일을 secrets.h 로 복사해 실제 값을 넣습니다. secrets.h 는 .gitignore 로 커밋되지 않습니다.
// secrets.h 가 없으면 이 예시 값으로 빌드되며, SSID 가 비어 있어 STA 접속을 하지 않습니다.

#define CAM_ROBOT_ID "A"            // "A" 또는 "B"
#define CAM_WIFI_SSID ""            // 시연 전용 공유기 SSID
#define CAM_WIFI_PASSWORD ""
#define CAM_AP_PASSWORD ""          // 점검용 AP 비밀번호(8자 이상, 비우면 AP 안 켬)
#define CAM_ACCESS_KEY ""           // 비우면 키 없이 접근(전용 공유기 안에서만 쓰는 경우)
// #define CAM_STATIC_IP "192.168.50.21"
// #define CAM_STATIC_GATEWAY "192.168.50.1"
// #define CAM_STATIC_NETMASK "255.255.255.0"
