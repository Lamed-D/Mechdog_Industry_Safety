# 관리자 대시보드

시연 시나리오([demo-scenario.md](demo-scenario.md) 5절)의 관리자 화면입니다. 두 단계로 만듭니다.

| 단계 | 폴더 | 내용 | 상태 |
| --- | --- | --- | --- |
| WP-D2 | `dashboard/core/` | 핵심 상태·사람 조작·사건 기록(웹 없이 테스트) | 완료(PC 테스트) |
| WP-D3 | `dashboard/web/` | 웹 서버·화면, 로봇 링크·영상 어댑터 | 진행 예정 |

## 1. 핵심 상태 (`dashboard/core`)

`DashboardCore(scenario, links, log)`가 시나리오 상태기계(`scenario/machine.py`), 로봇별 링크(`host/robot_link.RobotLink`),
사건 기록(`EventLog`, SQLite)을 묶습니다. 네트워크·웹 의존성이 없습니다.

| 조작 | 메서드 | 규칙 |
| --- | --- | --- |
| **전체 정지** | `estop_all()` | 확인 없이 바로. 모든 링크에 ESTOP을 걸고 즉시 한 번 보냄. 링크 하나·시나리오·기록이 실패해도 나머지는 계속하고, 실패 목록을 돌려줌(화면에 크게 표시) |
| 래치 해제 | `reset_latch(robot, confirmed=True)` | 확인 창을 거친 경우만. 신선한 래치 텔레메트리·배터리 조건은 링크가 검사. 실제 해제는 로봇 텔레메트리로 판단 |
| 알림 확인·안내 시작·재시도·조치 완료·순찰 시작·안내 재개 | `operator(event)` | 시나리오가 거부하면 `ok: False`와 이유 |
| 안내 멈춤 | `guide_blocked(reason)` | |

| 입력 | 메서드 | 처리 |
| --- | --- | --- |
| 링크 상태(10 Hz) | `update()` | 텔레메트리가 신선하고 래치가 풀리면 `robot_ready`. 끊기면 `link_lost`. **준비된 로봇이 스스로 래치되면**(저전압·감시 타이머 등) `robot_latched` 알림과 함께 준비 상태에서 뺌. 시나리오 시간 초과 처리 |
| 영상 감지 | `detection(result, zone)` | `host.vision.EvidenceMonitor` 결과. 알림 목록에 추가 |
| 도착 | `arrived(robot, target)` | 경로 실행 어댑터(D3)가 알림 |
| 카메라 수신 상태 | `camera_state(robot, state)` | `LatestFrameReceiver.state()`. 영상 없으면 `unknown` 표시 |

- 시나리오의 이동 명령(순찰·이동·안내·동작·자세)은 여기서 실행하지 않고 `drain_commands()`로 어댑터(D3)가 가져갑니다.
  `estop` 명령만은 어댑터를 기다리지 않고 바로 링크에 겁니다.
- `snapshot()`은 화면용 JSON(단계, 로봇 상태, 알림, 최근 알림 100개, 기록 실패 수)입니다.

## 2. 사건 기록 (`EventLog`)

- SQLite 한 표(`events`: 시각, 종류, 로봇, JSON 내용). 경로는 실행 시 지정, 기본은 메모리.
- 영상·사진 **바이트는 저장하지 않습니다**(`<bytes omitted>`로 바뀜). 필요하면 저장소 밖 로컬 경로 문자열만 남깁니다.
- 기록 실패는 예외 대신 실패 횟수로 알리며, 전체 정지 같은 조작을 막지 않습니다.
- 기록 파일은 현장 정보가 담기므로 저장소에 올리지 않습니다(`/logs/`, `outputs/`는 .gitignore).

## 3. 확인하지 못한 것

- 실제 RobotLink·로봇과의 연결, 10 Hz 갱신에서의 지연, 장시간 SQLite 크기. D3 어댑터와 실물 시험에서 확인합니다.
