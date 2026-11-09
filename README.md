# Mechdog Industry Safety

MechDog 사족보행 로봇을 활용한 산업 현장 안전 프로젝트입니다.

## 시연 시나리오

로봇 2대가 현장을 지키다가 카메라로 쓰러진 사람을 발견하면 대시보드로 관리자에게 알리고,
그중 1대가 관리자 위치(사무실 등)로 가서 관리자를 사고 지점까지 안내해 조치하게 합니다.
→ [docs/demo-scenario.md](docs/demo-scenario.md)

## 하드웨어 구성

- Hiwonder MechDog (ESP32, MicroPython) **2대**, 둘 다 같은 구성
- 다리 4개(사족보행)
- 앞쪽 비전 모듈(ESP32-S3 카메라)
- 팔·집게 없음
- 등 위 RPLIDAR A1M8-R6 라이다(테이프 고정)
- 처리: 고정 위치의 Raspberry Pi 5 16GB (부족하면 Jetson Orin Nano Super), 로봇과 Wi-Fi 통신
- 그 밖의 추가 센서(비공식) 장착 예정 — [배선 표](docs/dev/mechdog-api.md#63-배선-기록)

> 프로젝트 목표와 실행 방법은 아직 정리 중입니다.

## 개발 규칙

- [docs/README.md](docs/README.md): 브랜치·이슈·코드 리뷰·AI 작업 규칙
- AI 에이전트: [AGENTS.md](AGENTS.md), [CLAUDE.md](CLAUDE.md)
