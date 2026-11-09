# 에이전트 협업 규칙 (Claude · Codex)

이 저장소에서는 AI 에이전트 **두 개 — Claude(Claude Code)와 Codex(OpenAI Codex CLI)** 가 동시에 작업합니다.
두 에이전트는 서로의 대화 내용을 모르므로, 협업은 **GitHub(브랜치·이슈·PR)와 이 문서**로만 합니다.

## 1. 내가 누구인지

- Claude Code로 실행 중이면 **Claude**, Codex CLI로 실행 중이면 **Codex** 입니다.
- 사용자가 다른 이름이나 역할을 지정하면 그 지시를 따릅니다. 애매하면 작업 전에 묻습니다.

## 2. 작업 공간은 따로

- 두 에이전트는 **서로 다른 폴더(git worktree)** 에서 작업합니다. 같은 폴더를 함께 쓰지 않습니다.

| 에이전트 | 작업 폴더 (기본) |
| --- | --- |
| Claude | `C:\Users\Lamed\Documents\GitHub\mechdog-safety-claude` |
| Codex | `C:\Users\Lamed\Documents\GitHub\mechdog-safety-codex` |

- 원본 폴더(`Mechdog_Industry_Safety`)는 사용자 전용입니다. 에이전트는 여기서 파일을 고치거나 브랜치를 바꾸지 않습니다.
- 다른 에이전트의 작업 폴더에 들어가 파일을 읽거나 고치지 않습니다. 상대 작업은 GitHub의 브랜치·PR로만 봅니다.

## 3. 담당 영역

| 영역 | 담당 | 폴더 |
| --- | --- | --- |
| 로봇(MechDog ESP32, MicroPython) 쪽 코드 | **Claude** | `robot/`, `custom_sensors/`, `tests/fakes/`, `tools/bringup/` |
| 로봇 ↔ Pi 5 통신 규약 문서 | **Claude** (Codex는 PR 리뷰로 의견) | `docs/protocol.md` |
| Pi 5(호스트) 쪽 코드: 라이다 수신, ROS 2, 로봇 명령, 카메라, 대시보드 | **Codex** | `host/`, `ros2/`, `tools/mock/` |
| 공용 규칙 문서 | 사용자 승인 후 한 에이전트만 | `docs/dev/*`, `AGENTS.md`, `CLAUDE.md`, `.github/*`, `.claude/`, `.codex/` |

- 상대 담당 폴더의 파일은 고치지 않습니다. 필요하면 이슈나 PR 코멘트로 요청합니다.
- 테스트는 각자 자기 폴더 기준으로 `tests/` 아래에 둡니다(예: `tests/robot/`, `tests/host/`).

## 4. 작업 표시

- **PR 본문 첫 줄**에 `작업자: Claude` 또는 `작업자: Codex`를 적습니다.
- 커밋 본문 마지막에 `Agent: Claude` / `Agent: Codex` 줄을 넣습니다.
- 이슈를 맡을 때는 이슈에 `Claude 작업 시작` 같은 코멘트를 남깁니다.

## 5. 충돌 막기

1. 시작 전에 `git fetch`, `gh pr list`, `git branch -r`로 겹치는 작업이 있는지 봅니다.
2. 다른 에이전트의 브랜치에 커밋·푸시하지 않습니다.
3. 브랜치는 [브랜치 규칙](branch-rules.md)대로 `feat/<설명>`, `issue/<번호>-<설명>`. 이름이 겹치지 않게 합니다.
4. 공용 규칙 문서는 사용자 승인 없이 고치지 않습니다.

## 6. 서로 리뷰

- Claude의 PR은 Codex가, Codex의 PR은 Claude가 [코드 리뷰 규칙](code-review.md)대로 리뷰합니다.
- 리뷰는 PR 코멘트(`gh pr comment`, `gh pr diff`)로 남깁니다. **승인·병합은 사용자만** 합니다.

## 7. 실제 로봇 사용

- 로봇은 **2대(로봇 A, 로봇 B)** 입니다([시연 시나리오](../demo-scenario.md)). 에이전트와 로봇은 별개입니다.
- 실제 로봇에 프로그램을 올리거나 움직이는 일은 **사용자 확인을 받은 에이전트만**, 확인받은 로봇에만 합니다.

## 8. 비공개 자료

- [비공개 자료 규칙](confidentiality.md)을 따릅니다. 참고한 외부 저장소·자료의 이름·경로·코드·문구를
  커밋·PR·이슈·문서에 남기지 않습니다.
