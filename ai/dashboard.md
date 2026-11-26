# PC 대시보드 (`dashboard/`)

Windows 노트북 브라우저에서 로봇 **한 대**를 조종하고 카메라 영상·로봇 상태·LiDAR 점을 한 화면에서 보는 도구입니다.
현재 구성(로봇 1대 + RPLIDAR A1M8 + 앞쪽 ESP32-S3 비전 모듈 + 노트북 1대)의 유일한 PC 화면이며,
**앞으로 설계할 새 시연 시나리오의 기반**입니다([scenario.md](scenario.md)).

관련: [protocol.md](protocol.md)(UDP·TCP·HTTP 규약), [firmware.md](firmware.md)(메인 보드·비전 모듈 펌웨어), [hardware.md](hardware.md), [lidar-frozen.md](lidar-frozen.md), [robot-tests.md](robot-tests.md)

## 1. 구조

```text
브라우저(index.html) ⇄ HTTP 127.0.0.1:8090 ⇄ dashboard/server.py ⇄ UDP 9100/9101 ⇄ 로봇 메인 보드
                      ⇠ 카메라 MJPEG(브라우저가 --cam URL을 직접 표시)  ⇠ 비전 모듈
                      ⇠ /api/lidar ⇠ dashboard/lidar/feed.py ⇠ USB(A1M8 어댑터) 또는 TCP 20108(로봇 중계)
                      ⇠ /api/camera ⇠ dashboard/usb_camera.py ⇠ 비전 모듈 USB 시리얼(진단용)
```

| 파일 | 역할 |
| --- | --- |
| [`dashboard/server.py`](../dashboard/server.py) | HTTP 서버 + 명령 루프. `ConsoleLink`(= `robot_link.py`의 `RobotLink` + 일어서기), `AutoTransport`(방송으로 로봇 찾기) |
| [`dashboard/index.html`](../dashboard/index.html) | 화면. 요청마다 파일을 다시 읽으므로 수정은 새로고침만으로 반영 |
| [`dashboard/robot_link.py`](../dashboard/robot_link.py), [`udp_transport.py`](../dashboard/udp_transport.py), [`roles.py`](../dashboard/roles.py) | 규약 송수신·호스트 쪽 안전([protocol.md](protocol.md) 5.6절), UDP 소켓, 두 대 역할 조정(현재 미사용) |
| [`dashboard/lidar/`](../dashboard/lidar/) | `feed.py` `LidarFeed`(최신 한 회전만 보관), `probe.py`(USB·TCP 단독 확인), `rplidar_protocol.py`·`scan_assembler.py`·`tcp_client.py`·`laser_scan.py`(A1M8 표준 스캔 수신, [lidar-frozen.md](lidar-frozen.md)) |
| [`dashboard/usb_camera.py`](../dashboard/usb_camera.py) | `UsbCamera`: 비전 모듈 USB에서 JPEG 한 장씩 요청(115200 bps, `frame` 명령, 최대 128 KB, 제한 16초) |

브라우저는 UDP를 못 보내므로 `server.py`가 규약대로 HELLO/MOVE/STOP/ESTOP/RESET/POSE를 보냅니다. 서버는 `127.0.0.1`에만 엽니다.
명령 루프는 20 ms마다 TEL을 받고 `link.step()`을 부릅니다(송신 주기 100 ms는 `RobotLink`가 지킴).
기본 영상은 표시용입니다. Wi-Fi 감시 옵션을 켜면 서버가 최신 프레임을 공유합니다. 영상 없음·오래됨은 감지 불가입니다([protocol.md](protocol.md) 11절).

## 2. 실행

모든 명령은 저장소 최상위에서 실행합니다. 화면은 `http://127.0.0.1:8090`(포트는 `--port`로 변경).

| 목적 | 명령 |
| --- | --- |
| 실물, 제조사 기본 영상 펌웨어 AP | `python -m dashboard.server --robot A --robot-ip auto --allow-real --cam http://192.168.5.1:81/stream` |
| 실물, Windows 모바일 핫스팟 | `python -m dashboard.server --hotspot --allow-real` (USB LiDAR는 `--lidar-usb COM번호` 추가) |
| 실물, IP 지정 + LiDAR 로봇 중계 | `python -m dashboard.server --robot A --robot-ip %ROBOT_IP% --allow-real --cam %CAM_URL% --relay-lidar` |
| 실물 LiDAR만 USB로 | `.private\lidar-pc\Scripts\python.exe -m dashboard.server --lidar-usb COM번호` (로봇 IP 기본 루프백이라 실물 명령 없음) |
| 센서 전용(인터넷 Wi-Fi 유지, 로봇 UDP 소켓 없음) | `.private\lidar-pc\Scripts\python.exe -m dashboard.server --sensors-only --cam-usb COM카메라 --lidar-usb COM라이다 --port 8091` |

확인 순서: 부팅 잠금 표시 → 영상 → LiDAR 점 → 잠금 해제 → 이동 버튼을 눌렀다 놓아 이동·정지 → 비상 정지 후 잠김.

USB 장치(LiDAR·카메라)를 쓰려면 `pyserial`이 있는 로컬 환경이 필요합니다(커밋되지 않는 폴더):

```cmd
python -m venv .private\lidar-pc
.private\lidar-pc\Scripts\python.exe -m pip install pyserial
```

### 2.1 `dashboard.server` 플래그

| 플래그 | 기본값 | 뜻 |
| --- | --- | --- |
| `--robot` | `A` | 로봇 ID(`A`/`B`) |
| `--robot-ip` | `127.0.0.1` | 로봇 IP. `auto`면 방송으로 HELLO/STOP을 보내고 처음 답한 해당 ID 로봇(송신 포트 9100)의 IP로 고정. 고정 전에는 그 로봇 TEL 외에 받지 않음 |
| `--broadcast` | `192.168.5.255` | `auto`용 방송 주소(기본 영상 펌웨어 AP 기준) |
| `--hotspot` | 꺼짐 | 본체 IP와 방송 주소 기본값을 `auto`, `192.168.137.255`로 설정. 카메라를 지정하지 않으면 로봇 ID에 해당하는 `mechdog-<id>-cam.local`의 `/status`에서 영상 주소 확인. 조회 실패 시 같은 이름의 81번 포트 사용 |
| `--allow-real` | 꺼짐 | 루프백이 아닌 실제 로봇에 보내기 허용. `auto`에는 필수 |
| `--sensors-only` | 꺼짐 | 카메라·LiDAR만 표시, 본체 UDP 없음. `--allow-real`과 함께 불가 |
| `--cam URL` / `--cam-usb COM` | 없음 | 카메라 영상 주소 / USB JPEG 펌웨어가 든 비전 모듈. 둘 중 하나만 |
| `--monitor` | 꺼짐 | Wi-Fi 영상 사람 감지·초음파 정지(3절) |
| `--greet` | 꺼짐 | `--monitor`와 함께. 사람을 새로 보면 멈춘 뒤 인사(3절) |
| `--patrol-arrive-mm MM` | 없음 | **임시 시험.** 자율주행 "선 없음 · 태그 접근" 모드에서 목표 태그가 보이면 `move(50, 회전 ±10)`으로 직진하고, 직진 중에는 새 프레임을 기다리지 않고 매 주기 명령을 이어 보냄(태그를 2초 넘게 놓치면 중단, 초음파 값이 없어도 시작·직진을 막거나 중단하지 않음 — 값 없음 정지 규칙(mechdog-api.md 8절)을 이 시험 모드에서만 사용자 결정으로 해제, ❌ 기록에는 해결법 표시, 시작·종료 사유도 기록, 순찰 중 배터리 경고는 3초 넘게 계속될 때만 중단, 같은 순서로 다시 시작하면 멈춘 태그부터 이어서 가고 기록 유지(**처음부터 다시 시작** 버튼 = 시작 요청 `fresh: true`로 진행·기록 비우고 첫 태그부터), 다음 태그는 찾을 때까지 시간 제한 없이 제자리 회전). 전방 초음파가 `MM` 이하가 되면 멈추고, 멈춘 뒤 0.8초가 지나 찍힌 프레임에서 태그 하나·예상 ID를 확인. 300~1500. 태그가 보일 때 이미 `MM` 이하면 전진 없이 도착 확인으로 넘어감. 초음파 없음은 중단. 시작 시·주행 중 300 mm 막힘은 이 규칙이 대신하며 `MM` 이하에서는 전진하지 않음. 도착 기준 저장 불필요. 자율주행 탭 오른쪽 **도착 확인** 칸에 이번 순찰의 발견(구간마다 목표 태그를 처음 본 순간, 회전→직진 전환)·도착·중단 기록을 최신순 목록(최대 30건)으로, 각 기록 순간의 인식 화면(`/api/patrol/arrival/<n>`, 메모리만, 저장 안 함)과 함께 표시. 새 순찰을 시작하면 비움. 실물 미검증 |
| `--port` | `8090` | 웹 포트 |
| `--lidar-usb COM` / `--lidar-tcp HOST` / `--relay-lidar` | 없음 | LiDAR 입력. 셋 중 하나만. `--relay-lidar`는 `--robot-ip`와 같은 본체의 TCP 중계이며 `auto`와 함께 불가 |
| `--lidar-port` | `20108` | LiDAR TCP 포트 |

카메라와 LiDAR의 COM 포트는 달라야 합니다. USB 진단 도구(`dashboard.lidar.probe`)나 시리얼 모니터와 같은 포트를 동시에 열지 않습니다.

## 3. 화면과 안전 동작

### 쓰러짐 로그

`--fall-detection`은 Wi-Fi 입력에서 동작하며 센서 전용 또는 기존 `--monitor`와 함께 사용할 수 있습니다. EfficientDet Lite0에서 person 점수 0.55 이상인 최대 네 사람을 고르고, 각 영역에서 Pose Landmarker Lite로 관절을 추정합니다. 어깨·골반·다리의 가시성과 몸통 기울기 및 가로세로 비율로 누운 자세를 선별합니다. 정면 방향으로 누워 몸통이 짧게 보이거나 관절이 가려지면 놓칠 수 있습니다.

본체 연결 중 실제 감지를 확정하면 대시보드 제어 잠금 안에서 이동·대기 자세·잠금 해제 요청을 취소하고 기존 STOP 전송을 예약합니다. 30초 동안 이동·일어서기·잠금 해제를 거절하고 이전 입력 세대를 무효화합니다. 비상 정지는 항상 가능합니다. 시연 사진 리플레이는 별도 모델 인스턴스와 DB를 사용하고 정지 콜백이 없습니다.

영상 위치가 겹치는 관측을 같은 대상으로 연결합니다. 연이어 처리한 두 새 프레임의 자세가 일치하면 기록하며 1초 넘는 공백은 연속 확인을 끊습니다. 30초 이내 중복 및 계속 누운 상태를 억제합니다. 가림과 카메라 이동으로 트랙이 바뀔 수 있습니다.

%LOCALAPPDATA%/MechDog/fall-events.sqlite3에 사건과 박스 JPEG 두 장을 한 트랜잭션으로 보관합니다. 각 사진에는 수신 시각·크기·픽셀 박스 좌표가 있습니다. 로그 조회는 감지 옵션 없이도 가능합니다. GET /api/falls는 id 내림차순 25건이며 before로 이전 페이지를 읽습니다. GET /api/falls/{id}/photos/{0 또는 1}은 JPEG를, POST /api/falls/{id}/review는 verdict와 note를 처리합니다.

### 순찰 시나리오 첫 시연

두 로봇은 전용 실행 옵션 `--team A_IP B_IP --allow-real`로 시작합니다. 협동 탭은 `/api/state`의 `team`, 로봇별 `/api/team/frame/A`·`/api/team/frame/B`, 로컬 POST `/api/team/{start,heartbeat,stop,estop,finish,reset,calibrate}`를 사용합니다. 웹 세션이 1초간 갱신되지 않으면 전체 정지합니다. 동일 서버의 단일 조종 경로에는 본체 링크를 배정하지 않습니다. [사건 처리](scenario.md#8-두-로봇-협동-시나리오)

자율주행 탭은 Wi-Fi MJPEG 수신기 하나를 조종 화면·감지기와 공유합니다. 노트북의 별도 스레드가 새 프레임의 선·띠·tag36h11을 분석하고 제어 루프가 기존 RobotLink로 이동합니다. 센서 전용 모드는 미리보기·도착 기준 저장·태그 인쇄를 지원합니다. 설치와 코스 배치는 README의 자율주행 절을 따릅니다.

`/api/patrol/frame`은 인식 표시 JPEG, `/api/patrol/marker/<id>`는 인쇄용 PNG입니다. 시작·화면 연결 유지·도착 기준 저장은 로컬 JSON POST를 사용합니다. 시작 요청에는 주행 모드, 방문 ID 배열, 탐색 방향, 조종 화면 세션 ID와 현재 이동 세대 번호가 필요합니다. `/api/state`의 `patrol`은 현재 목표·방문 목록·저장된 기준·정지 사유를 제공합니다. 도착 기준은 영상 폭 대비 태그 평균 변 길이이며 노트북의 로봇별 SQLite 파일에 보관합니다.

실험 초기값은 영상 유효시간 1초, 화면 연결 만료 0.9초, 태그 제자리 탐색 최대 5초, 전방 초음파 정지 300 mm입니다. 새 분석 프레임마다 한 번만 이동 의도를 설정하고 기존 300 ms 만료를 적용합니다. 선 없는 모드에서 탐색 중에는 제자리 회전만 허용하고 접근 중 목표를 잃으면 중단합니다. 두 모드 모두 새로 시작하려면 사용자 입력이 필요합니다. 실물 주행 결과는 병합 후 사용자 확인 예정입니다.

Wi-Fi 카메라와 본체를 연결한 기존 실행 명령에 `--monitor`를 추가합니다. 실행에 쓰는 Python 환경에 `python -m pip install opencv-python-headless`로 감지 의존성을 설치합니다. 카메라 연결은 노트북에서 한 번만 열고, 화면에 수신 FPS·마지막 프레임 경과 시간·감지 상태를 표시합니다. 영상은 저장하지 않습니다.

사람이 연속 두 프레임에서 검출되거나 유효한 전방 거리가 30cm 이하가 되면 현재 입력을 취소하고 정지합니다. 새 방향 입력을 누르는 동안 수동으로 조종할 수 있습니다. 40cm 이상이면 전방 감지를 해제하고, 사람이 검출되지 않으면 사람 감지를 해제합니다. 영상 또는 거리 값이 끊기면 확인 불가로 표시하며 기존 경고는 유지합니다.

`--greet`를 더하면 사람을 새로 감지해 멈춘 뒤 인사합니다. 2초 안에 로봇이 잠금 해제된 `idle`이 되면(일어서기와 같은 조건) `CMD|ACTION|<id>|<seq>|scrape_a_bow|$`를 한 번 보냅니다. 로봇이 `action`을 거쳐 `idle`로 돌아오면 `POSE default`(`set_default_pose()`)를 한 번 보냅니다. 그 사이 방향을 누르고 있으면 보내지 않습니다. 로봇은 동작 중 `MOVE`를 받지 않고, 동작 뒤 첫 `MOVE` 전에 스스로 기본 자세를 잡습니다([protocol.md](protocol.md) 3.3).

- 보내기 전에 방향·정지·비상 정지를 누르거나, 사람이 사라지거나, 2초가 지나면 인사를 취소합니다.
- 래치·연결 끊김이면 추적을 끝냅니다. 이때 로봇은 `stop_action()`과 `move(0, 0)`을 실행합니다.
- 단순 정지(Space)는 진행 중인 동작 그룹을 끊지 않습니다. 끊으려면 비상 정지를 씁니다.
- `--fall-detection`의 30초 정지가 우선합니다. 정지 중에는 인사를 시작하지 않고, 쓰러짐을 확정하면 진행 중인 인사 추적과 복귀 자세 요청도 취소합니다.
- 인사가 끝나거나 포기한 뒤 10초([가정])는 다시 인사하지 않습니다. 사람이 계속 보이면 다시 인사하지 않고, 사라졌다 다시 보여야 인사합니다.
- 상태 줄에 "인사 준비 / 인사 중 / 인사 쉬는 중"을 표시합니다. 실물 미검증입니다.

경고 중 초음파 LED는 빨간색이고 수동 색 조절은 잠시 차단합니다. 모든 경고가 해제되면 직전 수동 색으로 돌아갑니다. 수동 색을 지정한 적이 없으면 끕니다. 30/40cm는 실물 시연용 초기값입니다. 감시가 꺼져 있으면 기존 조종과 카메라 동작을 사용합니다.

상단 표시줄에서 연결·잠금·배터리 상태와 비상 정지를 확인합니다. 그 아래 한 줄에 왼쪽부터 **카메라 | 로봇 상태(초음파 격자·LED 포함) | 조종** 세 칸을 둡니다. 카메라 칸은 4:3 영상 크기(화면 높이의 60% 기준)만큼만 차지하고, 남는 폭은 상태·조종 칸이 나눠 씁니다(상태 최소 300px, 조종 최소 360px). 조종 칸 맨 위에 잠금 해제·일어서기, 그 아래 현재 누른 방향과 로봇이 보고한 상태, 방향 패드(글자 한 줄), 슬라이더(이름은 슬라이더 위)가 있습니다. LiDAR는 아래 줄에 전체 폭으로 둡니다. 760px 이하 좁은 화면은 카메라 → 조종 → 로봇 상태 순으로 위아래로 쌓습니다.

방향 단축키는 페이지를 열면 꺼져 있습니다. 화면 맨 윗줄(비상 정지 왼쪽)의 **⌨ 방향 단축키** 스위치를 켜면(켜지면 파란색 강조) 바로 방향 키로 조종할 수 있고, 키보드로 이동하는 도중 끄면 정지합니다. 화면 버튼과 Space 정지, Esc 비상 정지는 토글과 관계없이 사용할 수 있습니다.

| 요소 | 동작 |
| --- | --- |
| 이동 | **누르고 있는 동안만.** 브라우저가 0.1초마다 `/api/move`를 다시 보내고, 서버 쪽 이동 의도는 0.3초(`HOST_INTENT_MS`) 뒤 사라져 `STOP`. W/A/S/D·화살표로 직진·제자리 회전, Q/E로 전진 좌·우회전, Z/C로 후진 좌·우회전, Space 정지, Esc 비상 정지 |
| 이동 값 | 보폭 슬라이더 5~100(기본 50), 회전 1~30(기본 15, 전진·후진 회전 Q/E/Z/C에만 적용), 제자리 회전 1~60(기본 60, A/D에만 적용). 각 값 옆에 흐린 글씨로 최대값("/ 100" 등). 전진·후진의 보폭은 각각 `s`, `-s`이고 제자리 회전의 보폭은 0입니다. 좌회전은 `a`(제자리는 제자리 회전 값), 우회전은 그 음수이며 보폭과 함께 기존 `move(step, angle)`로 전달합니다. 버튼을 누르는 즉시 브라우저가 첫 요청을 보내고, 서버는 다음 명령 주기에 전송 |
| 입력 전환 | 키나 포인터를 바꿔 누르면 마지막 입력이 방향을 정합니다. 이전 입력을 놓아도 새 입력은 유지되며, 현재 입력을 놓거나 화면을 떠나면 정지합니다. 신선한 TEL이 없거나 잠겨 있으면 화면과 서버가 이동 요청을 막습니다. |
| 잠금 해제 | 페이지 안의 확인창에서 확인하면 `RESET`. 확인창은 어두운 창에 노란(주의) 테두리, 굵은 질문 한 줄과 작은 안내 두 줄, 파란 [잠금 해제](Enter는 취소). 잠금 해제 버튼 바로 왼쪽에 뜨되 상단바(비상 정지 포함)는 가리지 않아, 창의 [잠금 해제]가 원래 버튼 약 24 px 왼쪽·조금 아래에 옴(같은 자리가 아니라 두 번 클릭으로 실수 확인 안 됨). 왼쪽 공간이 없는 좁은 화면은 버튼 아래. "해제 불가"·"일어서기 불가" 같은 안내는 잠금 해제·일어서기 버튼 바로 아래 한 줄에 표시(작은 노트북에서도 보이게). 신선한 래치 TEL과 배터리 `LOW_BATT_RESET_MV` 이상일 때만(아니면 400 오류). 해제돼도 움직이지 않음 |
| 일어서기 | 잠금 해제 뒤, 신선·비상정지 아님·`idle`·배터리 `LOW_BATT_WARN_MV` 이상·`batt_unknown`/`batt_low`/`lidar_uart`/`lidar_backlog`/`proto` 경고 없음일 때만 `CMD\|POSE\|<id>\|<seq>\|default\|$`(`set_default_pose()`)를 한 번 보냄. 정지·비상 정지·이동·종료·조건 깨짐이 대기 요청을 취소 |
| 비상 정지 | `ESTOP` 래치(호스트·로봇 양쪽). 이전 이동 의도 복원 없음 |
| 상태 | 연결(연결됨/응답 지연/로봇 응답 없음/비상 정지 중), 잠김, `state`, 래치 사유, 배터리 V, 기울기, **초음파 거리 cm**(TEL `sonar_mm`, 표시용), `warn`, 호스트 fault. 0.25초마다 `/api/state` |
| 초음파 거리 격자 | 로봇 상태 칸, LED 위. 제목 "초음파 · 로봇 정면" 바로 옆에 거리 수치(항상 흰색), 그 아래 "오래된 값"(TEL이 오래됐을 때)과 "표시용, 정지 판단에 쓰지 않음". 격자 칸 높이 300 px, 칸 실제 크기로 다시 그려 눈금 글씨 11 px 유지. 위 = 로봇 정면, 가로·세로 같은 축척의 정사각 격자(0.5·1·2·4 m 범위 버튼, 기본 1 m, 브라우저에 기억). 빔 ±15° [가정] 부채꼴 위에 측정 거리를 점선·굵은 선·cm 글자로 표시. 30 cm 미만 빨강·60 cm 미만 노랑(표시용). 범위 밖은 위쪽 "▲ 범위 밖", `NA`는 "측정 없음 — 장애물 없음이 아님", TEL이 오래되면 회색 |
| 초음파 LED | 제목 옆 알약에 현재 색(마지막으로 보낸 색, 감지 경고 중이면 "경고 · 빨강 고정"). 네모 견본 빨강·초록·파랑·흰색·끄기(금지 표시)와 색 직접 고르기(고른 뒤 창을 닫으면 적용, 적용 버튼 없음) → `POST /api/led {r,g,b}` → `CMD\|LED` 한 번. 신선한 TEL에 초음파 필드가 있을 때만 켜짐(잠김 중에도 가능, 움직이지 않음) |
| 이동 버튼 비활성 | TEL 없음·잠김·신선하지 않음·비상 정지 중. 누르는 중 이 상태가 되면 정지 |
| 카메라 | 제목 줄 오른쪽 끝에 **다시 연결** 버튼. 상태 문구는 연결 중·재연결 중이면 영상 칸 위쪽 가운데, 연결 실패·재시도 대기면 정가운데, 영상이 뜨면 사라짐. `--cam`이면 `<img>`로 MJPEG 직접 표시. `--cam-usb`면 0.75초마다 `/api/camera` JPEG(메모리에서만, 파일 저장 없음) |

카메라 오류 시 Wi-Fi 영상은 1초, 2초, 4초, 이후 8초 간격으로 다시 연결하고, USB 영상은 기존 0.75초 간격으로 요청합니다. **다시 연결**로 즉시 새 요청을 시작할 수 있습니다. Wi-Fi 영상이 오류 표시 없이 멈췄을 때도 이 버튼을 사용합니다.
| LiDAR | 0.25초마다 `/api/lidar`. 최신 한 회전을 점으로 그림. **표시 범위** 버튼 1·3·6·12 m와 캔버스 위 마우스 휠(0.5~12 m)로 확대·축소, 거리 링은 범위에 맞춰 3~6개, 위쪽 점선 = 센서 0°. 범위 밖 점은 숨기고 개수만 표시, 상태 줄에 가장 가까운 점 거리·센서 각도. 0.5 m 미만 점은 빨간색(표시용, 안전 판단 아님). 선택 범위는 브라우저에 기억(기본 6 m). 빈 각도·무효 측정은 비움. 1초 새 스캔 없음·연결 끊김이면 점을 지움(`stale`/`error`). **센서 원시 각도**라 로봇 정면과 맞는지는 장착 후 확인 |

- 대시보드의 `ConsoleLink`는 `require_scan=False`입니다. LiDAR가 끊겨도 이동이 막히지 않으므로, 안전은 로봇의 600 ms 감시와 래치에 기댑니다.
- 로봇은 켜지면 `boot` 래치 상태입니다. 통신이 끊기면 로봇이 스스로 멈추고 잠깁니다(`link_lost`). 배터리가 낮거나 모르면 이동 명령을 보내지 않습니다.
  세부 규칙은 [protocol.md](protocol.md) 5절.
- 서버 명령 루프에서 TEL 해석 오류(`ValueError`)는 `STOP`, 수신 소켓 오류(`OSError`)는 `ESTOP`, 송신 실패는 `RobotLink`가 ESTOP 래치. 서버 종료 시 `STOP`.

### 3.1 HTTP API (로컬 전용)

| 메서드 | 경로 | 내용 |
| --- | --- | --- |
| GET | `/` | 화면 |
| GET | `/api/state` | `robot`, `status`, `fresh`, `emergency`, `fault`, `error`, `cam`, `usb_camera`, `robot_ip`, `tel{state, latched, reason, battery_mv, tilt, warnings, last_seq}`. 센서 전용이면 `sensors_only: true` |
| GET | `/api/lidar` | `{status: disabled/waiting/stale/error/ready, source: USB/TCP, ranges_m: [m 또는 null…]}` |
| GET | `/api/camera` | `--cam-usb`일 때 최신 JPEG, 없으면 503 |
| POST | `/api/move` `{step, angle}`, `/api/stop`, `/api/estop`, `/api/stand`, `/api/reset` | 성공 `{ok: true}`, 조건 불충족 400 |

- `Host`가 정확히 `127.0.0.1:<포트>`이고 `Origin`이 없거나 같은 주소일 때만 응답(아니면 403). 다른 사이트의 브라우저 요청으로 로봇을 움직이지 못하게 합니다.
- POST는 `application/json`만(415), 본문 256바이트 이하(413), JSON 객체만(400). 소켓 제한 2초.

## 4. 네트워크 구성

| 구성 | 방법 | 상태 |
| --- | --- | --- |
| **제조사 기본 영상 펌웨어 AP** (현재 기본) | 비전 모듈이 개방형 2.4 GHz `HW_ESP32S3CAM`을 띄우고 `192.168.5.1`. 노트북과 로봇 모두 이 AP에 접속. 영상 `http://192.168.5.1:81/stream`, 상태 `http://192.168.5.1/status` | 로봇 B로 실물 확인(5절) |
| 맞춤 영상 펌웨어 + 공용 2.4 GHz 망 | 비전 모듈이 STA로 공유기·핫스팟에 붙음. 시리얼(115200, Newline)에서 `set robot A`, `set ssid`, `set pass`, `reboot`. `http://mechdog-a-cam.local/status`(안 되면 시리얼 상태 줄의 IP)로 확인 | 카메라 1대를 노트북의 2.4 GHz 핫스팟에 붙여 640×480 MJPEG 연속 수신 확인(펌웨어 0.1.8) |
| 센서 전용 USB | 비전 모듈 USB `frame` 명령 + LiDAR USB. Wi-Fi 불필요 | 진단용(한 장씩) |

- 기본 영상 펌웨어는 영상을 **한 화면에만** 보냅니다(두 번째 접속은 대기). 미리보기 탭을 닫고 대시보드는 한 탭에서만 엽니다.
- 기본 AP는 비밀번호가 없어 근처 누구나 영상을 볼 수 있습니다. 시험할 때만 켭니다. AP에 붙으면 노트북 인터넷이 끊기므로 필요하면 유선·USB 테더링을 씁니다.
- 인터넷을 유지하려면 Windows 11 모바일 핫스팟(공유 원본 Wi-Fi, 2.4 GHz)을 켜고 로봇·카메라를 그 핫스팟에 붙입니다.
  노트북 한 대에서 핫스팟을 켠 채 기존 Wi-Fi의 HTTPS 연결이 유지되는 것을 확인했습니다. 로봇 메인 보드의 핫스팟 참여와 장치 간 도달은 확인 필요.
  게스트망처럼 장치 간 통신이 막힌 망이 있으므로 IP 도달로 확인합니다.
- `auto`가 로봇을 못 찾으면 REPL에서 `network.WLAN(network.STA_IF).ifconfig()`로 IP를 보고 `--robot-ip`로 넣습니다.
- 처음 실행 때 Windows 방화벽 창이 뜨면 **개인 네트워크**만 허용합니다. 웹 포트는 루프백에만 둡니다. 핫스팟 이름·암호·주소는 로컬에서만 관리하고 커밋하지 않습니다.
- 로봇 한 대에는 명령 송신 프로세스 하나, LiDAR TCP 연결 하나만 둡니다(대시보드와 `dashboard.lidar.probe`를 같은 로봇에 동시에 붙이지 않음).
- 앞으로 로봇 두 대가 되면 운영자마다 자기 노트북에서 자기 로봇 ID로 대시보드를 하나씩 띄우는 구성을 기준으로 합니다(A/B 텔레메트리 포트가 같으므로 한 노트북에서 두 ID를 기본 포트로 동시에 띄우면 충돌).

## 5. 실물 확인 기록 (로봇 B, 사용자 실행)

- 비전 모듈을 기본 영상 펌웨어로 되돌린 뒤 PC·로봇 모두 `HW_ESP32S3CAM`에 연결, 화면에서 상태·영상 수신 확인.
- 받침대·바닥에서 전진·후진·좌·우·정지 동작 확인(사용자 관찰).
- 걷는 중 배터리가 낮아져 로봇이 `low_battery`로 스스로 잠김(쉬는 상태 약 7.2 V). 임계값은 가정값.
- 기울기는 `imu_unknown`(본체 시작 코드의 IMU 생성 인자 차이로 보임, 이동과 무관).
- LiDAR USB 직결: 장치 응답, 상태 0, 연속 스캔 3회, STOP 전송·포트 닫기 확인. 모터 정지 육안 확인·거리 정확도는 별도.
- 맞춤 펌웨어 카메라 1대 + 핫스팟: Wi-Fi 영상과 USB LiDAR를 센서 전용 화면에 동시에 표시.

미확인: Python Editor 연결 없이 전원만 켰을 때 자동 실행, J5 UART → Wi-Fi LiDAR 중계 실물(`--relay-lidar`), Wi-Fi를 끊었을 때 실물 정지·래치와 LiDAR 점 지움,
대시보드 종료 후 실물 정지 상태, 로봇 A, 두 대 동시 사용. 실물 확인은 사용자 승인 범위에서 받침대 위 잠금 해제 → 정지 → 비상 정지 순으로 시작합니다([robot-tests.md](robot-tests.md)).

## 6. 로봇에 올릴 파일 (MicroPython 판)

메인 보드 주 펌웨어는 MicroPython 판, Arduino 판은 예비입니다([firmware.md](firmware.md)). 둘 다 같은 규약이라 대시보드는 그대로 씁니다.

```cmd
python firmware/build.py A --only python
```

- `build/robot_A/python/`에 주석 없는 ASCII 파일 12개가 생깁니다(동작 코드는 `firmware/robot/python/`과 같음).
- 업로드 순서: `netutil` → `motion` → `roles` → `config` → `proto` → `vision` → `sonar` → `comm` → `lidar_bridge` → `core` → `app`, REPL에서 `import app` 확인, 마지막에 `main`.
- `secrets.py`(커밋 금지)는 `firmware/robot/python/secrets.example.py`를 참고해 장치에만 만듭니다. 기본 AP면 `WIFI_SSID = "HW_ESP32S3CAM"`, `WIFI_PASSWORD = ""`.
- 본체 업로드·기존 `main.py` 덮어쓰기는 **사용자만**(에이전트는 가이드 안내), 받침대 위에서, 복구 수단을 확인한 뒤 합니다.

## 7. LiDAR USB 단독 확인

```cmd
.private\lidar-pc\Scripts\python.exe -m dashboard.lidar.probe --usb COM번호
.private\lidar-pc\Scripts\python.exe -m dashboard.lidar.probe --tcp HOST [--port 20108] [--scans 3]
```

A1M8 장치 정보·상태·회전별 샘플 수를 출력하고 STOP을 보낸 뒤 닫습니다. USB는 라이다 모터를 구동합니다. 대시보드와 같은 포트를 동시에 열지 않습니다.
