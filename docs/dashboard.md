# 관리자 대시보드

시연 시나리오([demo-scenario.md](demo-scenario.md) 5절)의 관리자 화면입니다. 두 단계로 만듭니다.

| 단계 | 폴더 | 내용 | 상태 |
| --- | --- | --- | --- |
| WP-D2 | `dashboard/core/` | 핵심 상태·사람 조작·사건 기록(웹 없이 테스트) | 완료(PC 테스트) |
| WP-D3 | `dashboard/web/` | 웹 서버·화면(가짜 로봇 모드). 실물 링크·영상 어댑터는 다음 단계 | 화면·서버 완료, 실물 연결 남음 |

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

## 3. 웹 서버와 화면 (`dashboard/web`)

표준 라이브러리만 씁니다(`http.server` + 200 ms JSON 폴링). 새 의존성이 없습니다.

```bash
python -m dashboard.web.run --sim                  # 가짜 로봇 A·B, http://127.0.0.1:8000
python -m dashboard.web.run --sim --host 0.0.0.0 --token <조작 토큰> --log D:\mechdog-logs\events.db
```

- `--sim` 없이 실행하면 멈춥니다. 실물 링크(RobotLink + UDP, 두 로봇의 텔레메트리를 한 소켓에서 받아 로봇별로 나눔)는 다음 PR에서 붙입니다.
- 화면 맨 위 **전체 정지** 버튼은 확인 창 없이 바로 보내고, 실패하면 한 번 더 보낸 뒤 결과를 빨갛게 표시합니다.
- **전체 정지는 토큰 없이도** 받습니다(멈추는 쪽은 막지 않음). 순찰·안내 같은 조작과 래치 해제는 `--token`을 주면 토큰이 필요합니다.
- 래치 해제는 화면의 확인 창("주변이 안전하고 로봇을 지켜보고 있습니까?")을 거쳐야 하고, 서버도 `confirmed: true`만 받습니다.
- 서버와 연결이 끊기면 화면에 "정보가 오래됨"을 표시합니다. 로봇은 명령이 0.6초 끊기면 스스로 멈춥니다(규약 5.1절).
- 기본 주소는 127.0.0.1입니다. 관리자 노트북에서 열 때만 `--host`를 주고, 전용 공유기 안에서만 씁니다(HTTPS 아님).

## 4. 배포 결정 (사용자, 2026-11-09) — 다음 작업

| 항목 | 결정 | 할 일 |
| --- | --- | --- |
| 웹 서버 | **FastAPI + uvicorn** 사용 가능 | `dashboard/web/server.py`(현재 표준 라이브러리)를 FastAPI로 옮기고 화면 갱신은 WebSocket. 의존성은 `requirements-dashboard.txt`에 버전 고정·이유와 함께. `DashboardCore`·안전 규칙(전체 정지 토큰 없음, 래치 해제 확인)은 그대로 |
| 외부 접속 | **cloudflared**(Cloudflare Tunnel) | 대시보드는 계속 `127.0.0.1`에만 열고 cloudflared가 그 포트로만 연결. **Cloudflare Access(로그인) 필수**, 빠른 임시 터널(`--url`, 인증 없음)은 쓰지 않음. 카메라 스트림 포트·로봇 UDP·라이다 TCP는 터널에 넣지 않음 |
| 기록 DB | **Supabase**(Postgres) | `EventLog`와 같은 인터페이스(`record`/`recent`/`failures`)의 Supabase 판을 추가. **기록 실패·지연이 전체 정지를 막지 않게** 비동기 큐 + 로컬 SQLite 예비 기록 유지. 영상·사진 바이트는 올리지 않음 |

- Cloudflare 계정·터널 생성, Supabase 프로젝트·키 생성은 **사용자만** 합니다(비밀 정보). 키는 `.env`에만 두고 커밋하지 않습니다(`.env.example`에 이름만).
- 인터넷에 열리면 전체 정지 버튼도 인터넷에서 눌립니다. Access 로그인 뒤에만 열리게 하고, 로봇 쪽 정지(통신 끊김 0.6초)는 그대로 최종 안전 장치입니다.

## 5. 확인하지 못한 것

- 실제 RobotLink·로봇과의 연결, 10 Hz 갱신에서의 지연, 장시간 SQLite 크기. D3 어댑터와 실물 시험에서 확인합니다.
