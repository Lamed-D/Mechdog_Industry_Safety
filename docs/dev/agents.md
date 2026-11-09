# 에이전트 협업 규칙 (claude1 · codex1)

이 저장소에서는 AI 에이전트 **claude1(Claude Code), codex1(OpenAI Codex CLI), claude2(다른 사람이 쓰는 Claude Code)** 가 동시에 작업합니다.
두 에이전트는 서로의 대화 내용을 모르므로, 협업은 **GitHub(브랜치·이슈·PR)와 이 문서**로만 합니다.

## 1. 내가 누구인지

- **내 이름은 `git config --get agent.name` 으로 확인합니다.** 클론·worktree를 만든 사람이 처음에
  `python tools/setup_agent.py <이름>` 으로 정해 둡니다(이 작업 폴더에만 저장, 커밋되지 않음).
- 값이 비어 있으면 작업 전에 사용자에게 묻고, 직접 정하지 않습니다.
- 사용자가 다른 이름이나 역할을 지정하면 그 지시를 따릅니다. 애매하면 작업 전에 묻습니다.

## 2. 작업 공간은 따로

- 두 에이전트는 **서로 다른 폴더(git worktree)** 에서 작업합니다. 같은 폴더를 함께 쓰지 않습니다.

| 에이전트 | 작업 폴더 (기본) |
| --- | --- |
| claude1 | `C:\Users\Lamed\Documents\GitHub\mechdog-safety-claude` |
| codex1 | `C:\Users\Lamed\Documents\GitHub\mechdog-safety-codex` |
| claude2 | 다른 사람의 PC에 따로 클론한 폴더 ([claude2 안내](../agents/claude2.md)) |

- 원본 폴더(`Mechdog_Industry_Safety`)는 사용자 전용입니다. 에이전트는 여기서 파일을 고치거나 브랜치를 바꾸지 않습니다.
- 다른 에이전트의 작업 폴더에 들어가 파일을 읽거나 고치지 않습니다. 상대 작업은 GitHub의 브랜치·PR로만 봅니다.

## 3. 담당 영역

| 영역 | 담당 | 폴더 |
| --- | --- | --- |
| 로봇(MechDog ESP32, MicroPython) 쪽 코드 — Hiwonder 공식 Python 기반 | **claude1** | `robot/`, `custom_sensors/`, `tests/fakes/`, `tools/bringup/` |
| 로봇 ↔ Pi 5 통신 규약 문서 | **claude1** (codex1은 PR 리뷰·protocol 이슈로 의견) | `docs/protocol.md` |
| Pi 5(호스트) 쪽 코드: 라이다 수신, ROS 2, 로봇 명령, 카메라 | **codex1** | `host/`, `ros2/`, `tools/mock/` |
| 관리자 대시보드, 시연 시나리오 상태기계 | **claude2** | `dashboard/`, `scenario/`, `tests/dashboard/`, `tests/scenario/` |
| 공용 규칙 문서 | 대리 승인(9절) 후 한 에이전트만 | `docs/dev/*`, `AGENTS.md`, `CLAUDE.md`, `.github/*`, `.claude/`, `.codex/` |

- 상대 담당 폴더의 파일은 고치지 않습니다. 필요하면 이슈나 PR 코멘트로 요청합니다.
- 테스트는 각자 자기 폴더 기준으로 `tests/` 아래에 둡니다(예: `tests/robot/`, `tests/host/`).

## 4. 작업 표시와 소통

- 이슈 제목, PR 제목, 이슈·PR 코멘트, 사용자에게 하는 보고의 **맨 앞**에 `[내 이름]`(예: `[claude2]`)을 붙입니다.
- 사용자가 에이전트에게 일을 맡길 때도 `to:<이름>` + `agent:request` 이슈로 맡깁니다. 에이전트는 이 이슈를 읽고 작업합니다.
- PR 본문 첫 줄은 `작업자: <이름>`, 커밋 본문 마지막 줄은 `Agent: <이름>`.
- 에이전트끼리는 **GitHub 이슈**로 소통합니다. 라벨:
  - 보낸 쪽 `from:<이름>`, 받는 쪽 `to:<이름>`·`to:user` (claude1·codex1·claude2)
  - 종류 `agent:question`·`agent:request`·`agent:blocker`·`agent:info`, 주제 `protocol`
- 작업 단위를 끝낼 때마다, 새 작업을 시작하기 전에 `gh issue list --label "to:<내 이름>" --state open`으로 받은 이슈를 확인하고
  `[내 이름] 확인, <계획>` 코멘트를 남깁니다. 이슈는 연 쪽이 답을 확인한 뒤 닫습니다.
- 결정이 필요하면 `to:user` 이슈를 엽니다. 대부분은 **claude1이 사용자 대신 결정**합니다([9절](#9-사용자-대리-승인-claude1)).
  결정 전까지 그 부분은 추측으로 진행하지 않고, 다른 작업을 계속합니다.

## 5. 충돌 막기

1. 시작 전에 `git fetch`, `gh pr list`, `git branch -r`로 겹치는 작업이 있는지 봅니다.
2. 다른 에이전트의 브랜치에 커밋·푸시하지 않습니다.
3. 브랜치는 [브랜치 규칙](branch-rules.md)대로 `feat/<설명>`, `issue/<번호>-<설명>`. 이름이 겹치지 않게 합니다.
4. 공용 규칙 문서는 대리 승인(9절) 없이 고치지 않습니다.

## 6. 서로 리뷰하고 스스로 병합

PR은 사용자를 기다리지 않고 에이전트끼리 리뷰해서 병합합니다.

1. **리뷰:** PR은 작성자가 아닌 **다른 에이전트 한 명**이 [코드 리뷰 규칙](code-review.md)대로 리뷰합니다
   (기본: claude1 ↔ codex1, claude2의 PR은 담당 영역이 가까운 codex1, 바쁘면 claude1).
   리뷰는 PR 코멘트로 남기고 `[내 이름] 리뷰:`로 시작합니다. 두 에이전트가 같은 GitHub 계정을 쓰므로 GitHub의 "Approve" 기능은 쓰지 않고,
   승인은 코멘트 **`[내 이름] 리뷰: 승인`** 으로 표시합니다. 고칠 점이 있으면 `[차단]`/`[제안]`/`[사소]`/`[질문]`으로 적습니다.
2. **병합 조건 (모두 충족):**
   - 다른 에이전트의 `리뷰: 승인` 코멘트가 **마지막 커밋 이후에** 달려 있다(승인 뒤에 커밋을 더 올렸으면 다시 승인받는다)
   - 해결되지 않은 `[차단]`·`[질문]`이 없다
   - `python -m unittest discover -s tests` 통과(테스트가 있는 경우), `python tools/check_confidential.py range origin/main..HEAD` 통과
   - PR 제목·본문·코멘트에 참고 자료 이름·경로가 없다(직접 확인)
   - 이 PR과 관련된 `to:user` 이슈가 열려 있지 않다
3. **병합 방법:** PR **작성자**가 병합합니다. `gh pr merge <번호> --squash --delete-branch`.
   병합 뒤 상대에게 영향이 있으면 `agent:info` 이슈로 알립니다.
4. **공용 규칙·설정 파일을 바꾸는 PR**(`docs/dev/*`, `AGENTS.md`, `CLAUDE.md`, `.github/*`, `.claude/*`, `.codex/*`)은
   리뷰 승인에 더해 **대리 승인(9절)** 이 있어야 병합합니다. 보통은 codex1 리뷰 + claude1 대리 승인, claude1이 작성자면 codex1이 리뷰와 대리 승인을 함께 합니다.
   단 `tools/hooks/*`, `tools/check_confidential.py`(비공개 자료 검사 장치)를 바꾸는 PR은 **사용자만** 병합합니다.
5. 실제 로봇 동작이 바뀌는 PR은 병합해도 되지만, PR 본문에 "실물 미검증"을 분명히 적고 실물 확인 항목을 이슈로 남깁니다.
6. 상대가 리뷰를 못 하는 상태(오래 응답 없음)여도 자기 PR을 스스로 승인·병합하지 않습니다. `to:user` 이슈로 알립니다.

## 7. 실제 로봇 사용

- 로봇은 **2대(로봇 A, 로봇 B)** 입니다([시연 시나리오](../demo-scenario.md)). 에이전트와 로봇은 별개입니다.
- 실제 로봇에 프로그램을 올리거나 움직이는 일은 **사용자 확인을 받은 에이전트만**, 확인받은 로봇에만 합니다.

## 8. 비공개 자료

- [비공개 자료 규칙](confidentiality.md)을 따릅니다. 참고한 외부 저장소·자료의 이름·경로·코드·문구를
  커밋·PR·이슈·문서에 남기지 않습니다.

## 9. 사용자 대리 승인 (claude1)

사용자를 기다리지 않고 진행하도록, **claude1이 사용자 대신 결정·승인**합니다.

1. **claude1이 대신 정하는 것:** `to:user` 이슈의 질문과 결정(설계 선택, 공용 규칙 문서 변경 승인, 우선순위, 담당 조정),
   공용 규칙·설정 파일 PR의 병합 승인.
2. **방법:** 해당 이슈·PR에 `[claude1] 대리 승인: <결정과 이유>` 코멘트를 남깁니다. 승인한 이슈는 요청한 쪽이 확인한 뒤 닫습니다.
   - claude1 **자신이 요청한 결정**이거나 claude1이 작성한 공용 규칙 PR이면, claude1이 스스로 승인하지 않고
     **codex1이 `[codex1] 대리 승인:`** 으로 결정합니다(자기 승인 금지).
3. **확인 시점:** claude1은 [리뷰·병합 순환](#6-서로-리뷰하고-스스로-병합)을 돌 때마다 `gh issue list --label "to:user" --state open`도 확인합니다.
4. **대리 승인할 수 없는 것 (사용자만):** 아래는 `to:user` 이슈로 남기고 사용자를 기다립니다.
   - 실제 로봇에 프로그램·펌웨어를 올리거나 로봇을 움직이는 일
   - 돈이 드는 일(부품 구매, 유료 서비스)
   - 저장소 공개 범위·설정·협업자 초대, 저장소·브랜치 보호 설정, 저장소 삭제
   - 비공개 자료 검사 장치(`tools/hooks/*`, `tools/check_confidential.py`)와 비공개 낱말 목록 변경
   - 비밀 정보(Wi-Fi 비밀번호, 토큰)를 만들거나 바꾸는 일
5. 대리 승인한 결정은 사용자가 나중에 뒤집을 수 있습니다. 사용자의 직접 지시가 항상 우선합니다.
