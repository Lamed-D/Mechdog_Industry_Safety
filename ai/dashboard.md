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
영상은 **표시만** 합니다. 사람·낙상 판단은 없으며, 영상 없음·오래됨은 "사람 없음"이 아니라 감지 불가입니다([protocol.md](protocol.md) 11절).

## 2. 실행

모든 명령은 저장소 최상위에서 실행합니다. 화면은 `http://127.0.0.1:8090`(포트는 `--port`로 변경).

| 목적 | 명령 |
| --- | --- |
| 실물, 제조사 기본 영상 펌웨어 AP | `python -m dashboard.server --robot A --robot-ip auto --allow-real --cam http://192.168.5.1:81/stream` |
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
| `--allow-real` | 꺼짐 | 루프백이 아닌 실제 로봇에 보내기 허용. `auto`에는 필수 |
| `--sensors-only` | 꺼짐 | 카메라·LiDAR만 표시, 본체 UDP 없음. `--allow-real`과 함께 불가 |
| `--cam URL` / `--cam-usb COM` | 없음 | 카메라 영상 주소 / USB JPEG 펌웨어가 든 비전 모듈. 둘 중 하나만 |
| `--port` | `8090` | 웹 포트 |
| `--lidar-usb COM` / `--lidar-tcp HOST` / `--relay-lidar` | 없음 | LiDAR 입력. 셋 중 하나만. `--relay-lidar`는 `--robot-ip`와 같은 본체의 TCP 중계이며 `auto`와 함께 불가 |
| `--lidar-port` | `20108` | LiDAR TCP 포트 |

카메라와 LiDAR의 COM 포트는 달라야 합니다. USB 진단 도구(`dashboard.lidar.probe`)나 시리얼 모니터와 같은 포트를 동시에 열지 않습니다.

## 3. 화면과 안전 동작

| 요소 | 동작 |
| --- | --- |
| 이동 | **누르고 있는 동안만.** 브라우저가 0.1초마다 `/api/move`를 다시 보내고, 서버 쪽 이동 의도는 0.3초(`HOST_INTENT_MS`) 뒤 사라져 `STOP`. 키보드 W/A/S/D·화살표, Space 정지, Esc 비상 정지 |
| 이동 값 | 보폭 슬라이더 5~100(기본 20), 회전 1~30(기본 5). 앞 `move(s,0)`, 뒤 `move(-s,0)`, 좌 `move(s,a)`, 우 `move(s,-a)` — 좌·우는 **전진하면서** 회전(실물에서 쓴 값) |
| 잠금 해제 | `RESET`. 신선한 래치 TEL과 배터리 `LOW_BATT_RESET_MV` 이상일 때만(아니면 400 오류). 해제돼도 움직이지 않음 |
| 일어서기 | 잠금 해제 뒤, 신선·비상정지 아님·`idle`·배터리 `LOW_BATT_WARN_MV` 이상·`batt_unknown`/`batt_low`/`lidar_uart`/`lidar_backlog`/`proto` 경고 없음일 때만 `CMD\|POSE\|<id>\|<seq>\|default\|$`(`set_default_pose()`)를 한 번 보냄. 정지·비상 정지·이동·종료·조건 깨짐이 대기 요청을 취소 |
| 비상 정지 | `ESTOP` 래치(호스트·로봇 양쪽). 이전 이동 의도 복원 없음 |
| 상태 | 연결(연결됨/응답 지연/로봇 응답 없음/비상 정지 중), 잠김, `state`, 래치 사유, 배터리 V, 기울기, **초음파 거리 cm**(TEL `sonar_mm`, 표시용), `warn`, 호스트 fault. 0.25초마다 `/api/state` |
| 초음파 LED | 색 고르기 + 적용, 빨강·초록·파랑·흰색·끄기 버튼 → `POST /api/led {r,g,b}` → `CMD\|LED` 한 번. 신선한 TEL에 초음파 필드가 있을 때만 켜짐(잠김 중에도 가능, 움직이지 않음) |
| 이동 버튼 비활성 | TEL 없음·잠김·신선하지 않음·비상 정지 중. 누르는 중 이 상태가 되면 정지 |
| 카메라 | `--cam`이면 `<img>`로 MJPEG 직접 표시. `--cam-usb`면 0.75초마다 `/api/camera` JPEG(메모리에서만, 파일 저장 없음) |
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
