# claude2 — 할 일과 시작 프롬프트

claude2는 **다른 사람이 자기 PC에서 쓰는 Claude Code 에이전트**입니다. claude1(로봇 쪽), codex1(Pi 5 호스트 쪽)과 함께
GitHub 이슈·PR로만 협업합니다. 이 문서는 공개되어도 되는 내용만 담습니다.

## 1. 담당

| 영역 | 폴더 |
| --- | --- |
| 관리자 대시보드 (웹 화면 + 서버) | `dashboard/`, `tests/dashboard/` |
| 시연 시나리오 상태기계 (발견 → 알림 → 호출 → 이동 → 안내 → 조치 → 복귀) | `scenario/`, `tests/scenario/` |

- 다른 에이전트의 폴더(`robot/`, `custom_sensors/`, `tests/fakes/`, `tools/bringup/`, `docs/protocol.md` = claude1,
  `host/`, `ros2/`, `tools/mock/` = codex1)는 고치지 않습니다. 필요한 것은 이슈로 요청합니다.
- 로봇 명령은 `docs/protocol.md` 규약과 `docs/dev/mechdog-api.md`의 공식 동작 범위 안에서만 만듭니다.

## 2. 할 일 (작업 단위마다 브랜치 1개 → PR 1개)

### WP-D1 시나리오 상태기계 `scenario/`

- `docs/demo-scenario.md` 3·4절 흐름을 상태와 이벤트로 옮깁니다: 순찰, 발견, 알림, 호출, 이동, 안내, 조치, 복귀, 비상 정지.
- 입력 이벤트(사람 감지, 관리자 확인, 도착, 링크 끊김, 전체 정지, 조치 완료)와 출력(로봇별 고수준 명령, 대시보드 알림)을 정의합니다.
- 로봇 A·B 역할(발견 로봇·안내 로봇), 시간 초과, 감지 신뢰도가 낮을 때 "확인 필요" 처리, 링크 끊김·전체 정지 시 즉시 정지를 포함합니다.
- **표준 라이브러리만** 쓰고, 가짜 시계로 모든 전이를 테스트합니다.

### WP-D2 대시보드 핵심 상태와 기록 `dashboard/core/`

- 로봇 상태(텔레메트리), 알림 목록, 사람 조작(알림 확인, 안내 시작, 조치 완료, 래치 해제, 전체 정지)을 담는 상태 저장소.
- 사건 기록은 SQLite(표준 라이브러리 `sqlite3`)에 남깁니다. 현장 사진에는 사람이 찍히므로 저장소에 올리지 않고 로컬 경로만 기록합니다.
- 웹 프레임워크 없이 테스트할 수 있게 핵심 로직과 화면을 분리합니다.

### WP-D3 대시보드 서버와 화면 `dashboard/web/`

- 가벼운 웹 서버(FastAPI + WebSocket 권장, 의존성은 `requirements-dashboard.txt`에 이유와 함께)로 상태를 10Hz 안팎으로 화면에 보냅니다.
- 화면: 로봇 A·B 상태(단계, 래치, 배터리, 마지막 통신 시각), 알림 목록, 버튼(알림 확인, 안내 시작, 조치 완료, 래치 해제, **전체 정지**).
- 전체 정지는 가장 눈에 띄게, 확인 없이 바로 동작. 래치 해제는 확인 창을 거칩니다.
- 처음에는 가짜 데이터 어댑터로 동작하게 하고, codex1의 `host/robot_link`·영상 감지 이벤트와 연결하는 어댑터 인터페이스를 둡니다.
  인터페이스 모양은 codex1과 이슈로 합의합니다.

## 3. 처음 준비 (사람이 한 번)

1. 저장소 접근 권한: 저장소가 비공개이므로 관리자에게 GitHub 협업자 초대를 받습니다.
2. 클론과 이름 지정:

   ```bash
   git clone https://github.com/Lamed-D/Mechdog_Industry_Safety.git mechdog-safety-claude2
   ```

   ```bash
   cd mechdog-safety-claude2
   ```

   ```bash
   python tools/setup_agent.py claude2 --labels
   ```

3. 비공개 낱말 목록 `.confidential-terms`를 **관리자에게 비공개 경로로** 받아 작업 폴더 맨 위에 둡니다(저장소·이슈에 올리지 않습니다).
4. `python tools/setup_agent.py --show` 결과가 모두 채워졌는지 확인합니다.
5. `gh auth login`으로 GitHub에 로그인합니다.
6. 작업 폴더에서 Claude Code를 열고 아래 프롬프트를 붙여 넣습니다.

## 4. 시작 프롬프트 (claude2 세션에 붙여 넣기)

```text
너는 이 프로젝트의 claude2 에이전트다. 다른 에이전트는 claude1(로봇 쪽), codex1(Pi 5 호스트 쪽)이고, 모두 GitHub 이슈·PR로만 소통한다.

0. 시작 전 확인 (결과를 짧게 보고)
- `git config --get agent.name` 이 claude2 인지, `git config --get core.hooksPath` 가 tools/hooks 인지 확인한다.
- 작업 폴더 맨 위에 .confidential-terms 가 있는지 존재 여부만 확인한다(내용은 읽거나 출력하지 마라). 없으면 멈추고 알린다.
- `git fetch`, `gh auth status`, `gh pr list`, `gh issue list --label "to:claude2" --state open` 을 실행한다.
- 규칙 문서를 모두 읽는다: CLAUDE.md, docs/dev/agents.md, docs/dev/confidentiality.md, docs/dev/mechdog-api.md, docs/dev/ai-guide.md,
  docs/dev/branch-rules.md, docs/dev/code-review.md, docs/protocol.md, docs/demo-scenario.md, docs/lidar-integration.md, docs/agents/claude2.md.

1. 할 일
- docs/agents/claude2.md 의 WP-D1 → WP-D2 → WP-D3 순서로 진행한다. 나에게 할당된 이슈(to:claude2)가 있으면 그 내용을 우선한다.
- 담당 폴더(dashboard/, scenario/, tests/dashboard/, tests/scenario/) 밖은 고치지 않는다.

2. 표시와 소통
- 이슈·PR 제목, 코멘트, 나에게 하는 보고 맨 앞에 [claude2] 를 붙인다. PR 본문 첫 줄 "작업자: claude2", 커밋 마지막 줄 "Agent: claude2".
- 다른 에이전트에게는 이슈로 묻는다: gh issue create --title "[claude2] <요약>" --label "from:claude2,to:codex1,agent:question" ...
  (받는 쪽 to:claude1 / to:codex1 / to:user, 종류 agent:question / agent:request / agent:blocker / agent:info)
- 작업 단위를 끝낼 때마다, 새 작업 전에 to:claude2 이슈를 확인하고 "[claude2] 확인, <계획>" 코멘트를 남긴다.

3. 리뷰·병합 (docs/dev/agents.md 6절)
- 내 PR은 다른 에이전트 한 명의 "[이름] 리뷰: 승인" 코멘트(마지막 커밋 이후)와 테스트·비공개 낱말 검사 통과 후 내가 squash merge 한다.
- 다른 에이전트의 PR이 올라오면 code-review.md 기준으로 "[claude2] 리뷰:" 코멘트를 남긴다. 자기 PR은 스스로 승인하지 않는다.
- 공용 규칙·설정 파일(docs/dev/*, AGENTS.md, CLAUDE.md, .github, .claude, .codex, tools/hooks, tools/check_confidential.py)은 고치지 않는다.

4. 지켜야 할 것
- 커밋 형식 `<type>: <한국어 요약>` + 한국어 본문. 브랜치 feat/<설명>. 훅을 우회하지 않는다.
- 개인정보·비밀 정보·실제 현장 사진·외부 참고 자료의 이름과 경로를 커밋·PR·이슈·문서에 남기지 않는다.
- 실제 로봇에 명령을 보내는 실행은 사용자 확인 후에만 한다.
- 막히면 추측하지 말고 이슈로 묻는다. PR을 올릴 때마다 PR 링크, 테스트 결과, 검증하지 못한 것을 보고한다.

지금 0번부터 시작해라.
```
