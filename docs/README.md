# 문서

## 프로젝트

| 문서 | 내용 |
| --- | --- |
| [firmware-strategy.md](firmware-strategy.md) | 펌웨어 방침: 메인 보드 MicroPython 우선·Arduino 예비, 비전 모듈 Arduino |
| [lidar-integration.md](lidar-integration.md) | RPLIDAR A1M8 → MechDog J5(UART) → Wi-Fi → Pi 5 연동 설계, 배선표, 테스트 계획, 확인 필요 사항 |
| [vision-cam-firmware.md](vision-cam-firmware.md) | 비전 모듈(ESP32-S3 카메라) 맞춤 펌웨어: Pi 5로 영상 전송, 설치·Wi-Fi 설정·복구·빌드 |
| [dashboard.md](dashboard.md) | 관리자 대시보드: 인터넷·Supabase 기준 구조, Pi 5 핫스팟 로봇망, 명령 경로, 전체 정지·래치 해제·알림 처리 규칙, Android 알림 명세 |
| [mapping-and-patrol.md](mapping-and-patrol.md) | 운영 흐름: 정찰·지도 작성 → 사람이 대시보드에서 지도 확정(선택: 노트북 이미지 모델) → 구역 지정 → Pi 5 순찰 루틴(인터넷이 끊겨도 반복) |
| [demo-scenario.md](demo-scenario.md) | 시연 시나리오: 쓰러진 사람 발견 → 대시보드 알림 → 로봇이 관리자 안내, 구현 전 결정 사항 |

## 개발 규칙 (GitHub 기준)

| 문서 | 내용 |
| --- | --- |
| [dev/agents.md](dev/agents.md) | Claude·Codex 두 에이전트의 작업 폴더, 담당 영역, 충돌 방지, 교차 리뷰 |
| [agents/claude2.md](agents/claude2.md) | claude2(다른 사람의 Claude Code) 담당·할 일·준비·시작 프롬프트 |
| [dev/confidentiality.md](dev/confidentiality.md) | 참고 자료·개인정보를 기록에 남기지 않는 규칙과 자동 검사 |
| [dev/mechdog-api.md](dev/mechdog-api.md) | 모든 로봇 제어는 Hiwonder 공식 MechDog Python API 사용, API 요약, 포즈·동작 목록, 추가(비공식) 센서 규칙·배선 표 |
| [dev/branch-rules.md](dev/branch-rules.md) | 브랜치 `feat/`·`issue/` 규칙, 커밋 메시지, 병합 흐름 |
| [dev/issue-rules.md](dev/issue-rules.md) | 이슈 종류·라벨, 좋은 이슈 작성법, 현장 데이터 주의 |
| [dev/code-review.md](dev/code-review.md) | PR 작성, 리뷰 우선순위·체크리스트, 코멘트 형식, 병합 조건 |
| [dev/ai-guide.md](dev/ai-guide.md) | AI 에이전트용 프로젝트 요약·필수 규칙·작업 절차 |

GitHub 템플릿: [`.github/ISSUE_TEMPLATE`](../.github/ISSUE_TEMPLATE), [`.github/pull_request_template.md`](../.github/pull_request_template.md)
