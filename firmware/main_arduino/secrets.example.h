// Wi-Fi 이름·비밀번호와 로봇 ID. 실제 값은 secrets.h 에 두고 커밋하지 않습니다(.gitignore).
// 이 파일을 secrets.h 로 복사한 뒤 값을 채웁니다. 가짜 값만 예시로 둡니다.
#ifndef MECH_SECRETS_H
#define MECH_SECRETS_H

// 공통 로봇망(WPA2, 외부 인터넷 라우팅 금지). Windows 노트북 핫스팟 SSID/비밀번호와 같아야 합니다.
#define MECH_WIFI_SSID "mechdog-net"
#define MECH_WIFI_PASS "change-me-please"

// 이 로봇의 ID. 로봇 A 는 'A', 로봇 B 는 'B'. (docs/ai/protocol.md 2.1절)
#define MECH_ROBOT_ID 'A'

#endif
