# AI 작업 규칙

이 저장소는 여러 AI(Claude Code, Codex 등)가 함께 개발합니다. 사람은 [README](../README.md)만 봅니다.
AI가 읽을 규칙·설계·도구는 모두 이 폴더(`ai/`)에 둡니다.

## 1. 이름

- 내 이름은 `git config --get agent.name`(설정: `python ai/tools/setup_agent.py <이름>`). 비어 있으면 사용자에게 묻습니다.
- PR 제목·PR/이슈 코멘트·사용자 보고 맨 앞에 `[이름]`을 붙입니다.
- PR 본문 첫 줄 `작업자: <이름>`, 커밋 본문 마지막 줄 `Agent: <이름>`.
- 담당 영역은 나누지 않습니다. 시작 전에 `git fetch`, `gh pr list`, `git branch -r`로 겹치는 작업을 보고,
  다른 AI의 브랜치에는 커밋·푸시하지 않습니다.

## 2. 브랜치·커밋

- `main`에 직접 커밋하지 않습니다. 브랜치는 `feat/<설명>`(기능·문서·리팩터링·테스트) 또는
  `issue/<이슈번호>-<설명>`(버그). 설명은 영어 소문자 kebab-case 3~5단어.
- 한 브랜치에 한 주제. 이미 푸시한 브랜치는 rebase·force-push 하지 않습니다.
- 커밋: Conventional Commits, `type`은 영어, 요약·본문은 한국어.

  ```text
  feat: 한국어 요약 (50자 안팎)

  무엇을, 왜 바꿨는지.

  Agent: <이름>
  ```

  type: `feat` `fix` `docs` `test` `refactor` `chore`. 버그 수정은 본문이나 PR에 `Fixes #번호`.
- PR 제목도 같은 형식(`[이름] feat: ...`) — squash merge 커밋이 됩니다.

## 3. 병합 (자체 검증 후 직접)

다른 AI의 리뷰를 기다리지 않습니다. 아래를 모두 통과하면 작성자가 직접 병합합니다.

1. 바꾼 Python 파일이 `python -m compileall -q dashboard ai firmware/robot/python` 로 컴파일됨
2. `python tools/check_confidential.py range origin/main..HEAD` 통과
3. PR 제목·본문·코멘트에 비공개 참고 자료 이름·경로가 없음(직접 확인)
4. PR 본문에 검증하지 못한 것(실물 로봇 동작 등)을 적음
5. `gh pr merge <번호> --squash --delete-branch`

## 4. 로봇 제어는 공식 API만

- 관절·이동·자세·센서·출력 제어는 Hiwonder 공식 MechDog API로만 합니다
  (MicroPython: `HW_MechDog`, `Hiwonder`, `Hiwonder_IIC` / Arduino: 제조사 라이브러리).
- 직접 PWM·raw I2C·UART로 공식 장치를 구동하거나 자체 서보 드라이버·역기구학을 만들지 않습니다.
  예외: 추가 센서 **읽기**(라이다 중계 `firmware/robot/python/lidar_bridge.py`), 노트북과의 Wi-Fi 통신.
- 문서에 없는 메서드·인자를 지어내지 않고, 없는 장치(팔·집게·꼬리, `set_servo`)를 쓰지 않습니다.
- API에 없는 기능이 필요하면 우회 구현하지 말고 사용자에게 묻습니다.
- 자세한 표와 범위: [mechdog-api.md](mechdog-api.md).

## 4.1 펌웨어 올리기 역할

| 대상 | 누가 | 에이전트가 할 일 |
| --- | --- | --- |
| **로봇 본체**(메인 보드 MicroPython `.py` 업로드, `main.py` 덮어쓰기, Arduino 굽기, 구동) | **사용자만** | 업로드 파일·빌드를 만들고, [firmware.md](firmware.md) 2.2·4.2절 사용자 가이드를 최신으로 고치고, 작업 때 채팅으로 "이렇게 하세요" 순서를 안내 |
| **비전 모듈**(ESP32-S3 카메라) 굽기·설정·확인 | **에이전트가 직접** 해도 됨 | [firmware.md](firmware.md) 6.5절대로 수행 |

비전 모듈 작업 조건:

- 플래시 백업은 하지 않습니다(사용자 결정). 이미 맞춤 펌웨어가 있으면 앱(0x10000)만 구워 설정을 유지합니다. ERASE·전체 지우기 금지.
- 본체 전원 끄기, IIC 케이블 분리·복원, USB 연결 같은 **물리 조작은 사용자에게 요청**합니다.
- 포트가 카메라(CH340)인지 `flash-id`(ESP32-S3)로 확인하고, 메인 보드 포트에는 절대 쓰지 않습니다.
- **Wi-Fi 비밀번호**: 에이전트가 Windows에서 직접 얻어(`netsh wlan show profile name=<SSID> key=clear`, 모바일 핫스팟 설정 등) 시리얼로만 입력합니다.
  화면 출력·로그·파일·커밋·PR·이슈에 남기지 않습니다(필요하면 `.private/`에만 임시 보관 후 삭제). 명령 결과에서 비밀번호 줄은 걸러서 봅니다.
- 끝나면 채팅으로 사용자에게 알립니다: 대상 로봇 ID, 접속 SSID, 펌웨어 버전, IP, 점검용 AP 비밀번호(기본 `password`), 확인 결과.

## 5. 비공개 자료

- 참고한 외부 저장소·자료의 이름·주소·경로·코드·문구를 커밋·PR·이슈·문서 어디에도 남기지 않습니다.
  근거는 "제조사 예제", "제조사 회로도", "공개 데이터시트"처럼 일반 이름으로, 공식 공개 문서만 URL로 씁니다.
- 참고 자료는 저장소 밖이나 `.private/`·`refs/`·`references/`(gitignore)에 둡니다. 특정 이름을 무시하려면 `.git/info/exclude`.
- 커밋 훅(`git config core.hooksPath tools/hooks`)이 비공개 낱말을 막습니다. 훅을 끄거나 `--no-verify`로 우회하지 않습니다.
- `tools/hooks/*`, `tools/check_confidential.py`, `.confidential-terms`는 사용자만 고칩니다.
- 비밀 정보(Wi-Fi 비밀번호, 토큰)와 개인정보·사람 얼굴 영상은 커밋하지 않습니다. 예시는 `*.example.*`에 가짜 값으로.

## 6. 문서

- AI용 규칙·설계·도구는 `ai/`에, 사람용은 `README.md` 하나(짧게, 자세한 건 `ai/` 링크)만 둡니다.
  최상위에는 사람이 보는 소프트웨어(`firmware/`, `dashboard/`)와 `ai/`만 둡니다. `tools/`는 사용자 전용 커밋 훅 자리입니다.
- 코드를 바꾸면 관련 `ai/` 문서를 같은 PR에서 고칩니다. 새 문서를 늘리기보다 기존 파일에 합칩니다.

| 파일 | 내용 |
| --- | --- |
| [mechdog-api.md](mechdog-api.md) | 공식 API 규칙·표, 포즈·동작 목록, 추가 센서 규칙·배선 표, API 대조 |
| [hardware.md](hardware.md) | 장비 구성·전원·배선 |
| [protocol.md](protocol.md) | 로봇 ↔ 노트북 통신 규약, A/B 역할 |
| [firmware.md](firmware.md) | 메인 보드(MicroPython·Arduino) 사용자 업로드 가이드, 비전 모듈 펌웨어 빌드·굽기·복구 |
| [dashboard.md](dashboard.md) | 노트북 대시보드(`dashboard/`), 라이다 USB 확인 |
| [robot-tests.md](robot-tests.md) | 실물 확인 절차·결과 양식 |
| [`tools/`](tools/) | 에이전트 설정 스크립트 (펌웨어 빌드는 사람과 같은 [`../firmware/build.py`](../firmware/build.py), [firmware.md](firmware.md) 0절) |
| [lidar-frozen.md](lidar-frozen.md) | 라이다 — **동결**(표시만, 추가 개발 금지) |
| [scenario.md](scenario.md) | 새 시나리오 (설계 예정) |

## 7. 현재 범위

- 장비: MechDog 1대 + 앞쪽 ESP32-S3 비전 모듈 + 등 위 RPLIDAR A1M8, Windows 노트북 1대. 나중에 같은 세트 A/B 2대로 협업 확장.
- 메인 보드 펌웨어는 `firmware/robot/python/`(MicroPython, 주)과 `firmware/robot/arduino/` 둘 다 유지.
- 라이다는 USB 연결로 대시보드 표시 시연 수준으로 동결. 지도는 앞으로 VSLAM.
- 실장비로만 확인합니다. 가짜 장비·모의 서버·자동 테스트는 두지 않습니다.
