# 펌웨어 (메인 보드 · 비전 모듈)

로봇에는 프로그램이 올라가는 칩이 두 개 있습니다. 역할은 [rules.md](rules.md) 4.1절.

- **메인 보드(본체):** 업로드·굽기·구동은 **사용자만**. 에이전트는 업로드 파일·빌드를 만들고 2.2·4.2절 **사용자 가이드**를 고친 뒤 채팅으로 순서를 안내합니다.
- **비전 모듈(카메라):** 에이전트가 굽기·설정·확인까지 직접 합니다(6.5절, 백업 없음). 전원·케이블 같은 물리 조작만 사용자에게 요청합니다.

| 칩 | 위치 | 방식 | 폴더 | 상태 |
| --- | --- | --- | --- | --- |
| 메인 보드 ESP32(클래식) | 몸통 | **MicroPython(주)**, 순정 펌웨어 위에 `.py` 업로드 | [`firmware/robot/python/`](../firmware/robot/python/) | 주 펌웨어. 통합 main 실물 미검증 |
| 메인 보드 ESP32 | 몸통 | Arduino(C++), 예비·유지 | [`firmware/robot/arduino/`](../firmware/robot/arduino/) | 전체 이식 완료. 벤더 백엔드·실물 미검증 |
| 비전 모듈 ESP32-S3 | 앞쪽 카메라 | Arduino(C++) 맞춤 영상 펌웨어 | [`firmware/vision/`](../firmware/vision/) | v0.1.9(AP 기본 비밀번호만 변경). v0.1.8은 로봇 B 카메라에서 실물 동작 확인 |

## 0. 빌드 — 사람·AI 공통 도구 `firmware/build.py`

빌드 도구는 사람이 쓰는 것과 같은 것을 씁니다. 진입점은 [`firmware/build.py`](../firmware/build.py) 하나이며, 내부 모듈은 [`firmware/builder/`](../firmware/builder/)에 있습니다.
AI는 따로 스크립트를 만들지 않고 이 명령을 실행합니다. 결과는 로봇별로 `build/robot_<ID>/`에 모입니다(`build/`는 gitignore).

```powershell
python firmware/build.py A                           # 기본: python + vision
python firmware/build.py B --only python             # 본체 Python 파일만
python firmware/build.py A --only vision --profile detail
python firmware/build.py A --only arduino            # Arduino 판(예비) 컴파일 확인
```

| 대상 | 결과 폴더 | A/B 구분 | 다음에 누가 |
| --- | --- | --- | --- |
| `python` | `build/robot_<ID>/python/` (12개 .py) | `config.py`의 `ROBOT_ID` 치환 | **사용자**가 2.2절 순서로 업로드 |
| `vision` | `build/robot_<ID>/vision/latest/` 합본·`.sha256`·`manifest.json`(`robot` 기록) | 빌드 플래그 `CAM_BUILD_ROBOT_<ID>`가 카메라 기본 ID가 됨 | **AI**가 6.5절로 굽기 |
| `arduino` | `build/robot_<ID>/arduino/` | ID는 `secrets.h`의 `MECH_ROBOT_ID`(Wi-Fi와 같은 파일). 다르면 빌드가 멈춤 | **사용자**가 4.2절로 Arduino IDE 업로드 |

- 끝에 대상별 `[성공]/[실패]`와 다음 단계가 나옵니다. 하나라도 실패하면 종료 코드 1.
- `arduino-cli` 위치가 기본과 다르면 `ARDUINO_CLI`, esptool은 `ESPTOOL_PATH`. 이 PC: `C:\Program Files\Arduino IDE\resources\app\lib\backend\resources\arduino-cli.exe`.
- 에이전트의 Git Bash 샌드박스에서는 `build/`가 실제 폴더와 다르게 보일 수 있으니 빌드·확인은 PowerShell로 합니다.
- 개별 도구도 그대로 쓸 수 있습니다: `firmware/builder/make_robot_files.py <ID>`, `build_vision_cam.py [--robot <ID>] [--release] [--verify-release]`, `build_main_arduino.py [--robot <ID>]`. `--robot` 없이 만든 카메라 합본은 A/B 공통(`build/vision_cam/latest/`, ID는 시리얼로 설정).
- 사람에게 안내할 때는 [README](../README.md) "펌웨어 빌드" 절과 같은 명령을 알려 줍니다.

제조사 Scratch 방식은 쓰지 않습니다. 제어 API 규칙은 [mechdog-api.md](mechdog-api.md), 메시지 형식은 [protocol.md](protocol.md), 배선·전원은 [hardware.md](hardware.md), 실물 확인 순서는 [robot-tests.md](robot-tests.md).

## 1. 두 메인 보드 펌웨어가 지킬 것

- **같은 통신 규약:** `CMD|...|$` / `TEL|...|$`, UDP 9100(명령)/9101(텔레메트리), 라이다 TCP 20108 원시 중계. PC 쪽은 어느 펌웨어인지 몰라도 동작해야 합니다.
- **같은 안전 동작:** 명령 600 ms 끊김 시 정지·래치, ESTOP 최우선, 부팅 시 boot 래치(사람이 RESET 해야 해제), RESET 후 텔레메트리로 해제 확인, 저전압 정지, 범위 밖 값 자르기.
- **같은 제어 수단:** 제조사 공식 API(이동·자세·동작 그룹·균형)만. 서보 직접 구동 금지.
- 임계값을 바꾸면 `firmware/robot/python/config.py`와 `firmware/robot/arduino/mech_config.h`를 같이 고칩니다(PC 화면은 Python `config.py` 상수를 읽음).

| 설정 | 값 | 위치 |
| --- | --- | --- |
| 로봇 ID | `A` / `B` (현재 장비는 1대, 코드는 ID 유지) | `python firmware/build.py <ID>` (0절). Python: `ROBOT_ID` 치환 / 카메라: 빌드 기본값(시리얼 `set robot`이 우선) / Arduino: `secrets.h`의 `MECH_ROBOT_ID` |
| 통신 끊김·이동 유효시간 | 600 ms [가정] | `config.py` / `mech_config.h` |
| 저전압 경고/래치/해제 | 7000 / 6600 / 6800 mV [가정, 단위 mV 확인 필요] | 〃 |

## 2. 메인 보드 MicroPython (`firmware/robot/python/`, 주 펌웨어)

- 순정 펌웨어 MicroPython v1.21.0을 굽지 않고 유지, `.py`만 Hiwonder Python Editor로 올립니다. 되돌리기 쉽습니다.
- Wi-Fi 값은 장치 최상위 `secrets.py`에만 둡니다(`firmware/robot/python/secrets.example.py` 참고, 커밋·화면 공유 금지).

### 2.1 업로드 파일 만들기 (PC, 장치 접속 없음)

| 명령 | 결과 | 비고 |
| --- | --- | --- |
| `python firmware/build.py B --only python` | `build/robot_B/python/` 파일 12개(주석·설명문 제거, ASCII, 짧은 줄; 동작 코드 동일, `ROBOT_ID` 치환) | 업로드 방식. 이전 빌드의 남은 .py는 지움 |

### 2.2 업로드 순서 (사용자 가이드)

사용자가 그대로 따라 합니다. 에이전트는 이 절을 최신으로 유지하고, 업로드가 필요할 때 채팅으로 이 순서를 안내합니다.

0. 빌드: `python firmware/build.py <ID> --only python` → `build/robot_<ID>/python/`의 파일을 올립니다.

1. 로봇을 받침대에 올리고 다리 주변을 비웁니다. 편집기로 메인 보드에 연결, Ctrl+C로 자동 실행 중단. 본체와 카메라 COM 포트를 구분합니다.
2. `secrets.py`를 올립니다.
3. 순서대로 Download: `netutil` → `motion` → `roles` → `config` → `proto` → `vision` → `sonar` → `comm` → `lidar_bridge` → `core` → `app`, REPL에서 `import app` 확인, **마지막에 `main.py`**. 실행은 `import main` 또는 재부팅.
4. 첫 확인: 예외·MemoryError 없음, Wi-Fi 연결, 텔레메트리의 ID·boot 래치·배터리·경고. 처음에는 RESET·MOVE를 보내지 않습니다. MechDog 초기화 자체의 움직임은 실물 미검증입니다.
5. 문제 시 자동 실행을 멈추고 기존 `main.py`·설정을 되돌린 뒤 재시작. REPL 접근이 안 되면 반복 재부팅하지 말고 제조사 복구 절차로 순정 MicroPython을 복원합니다.

실물 확인 순서는 [robot-tests.md](robot-tests.md).

**스레드 구성(실물 근거, 2026-11-22 로봇 A):** 예전처럼 `startMain` 루프 4개를 띄우면 순정 펌웨어 + Wi-Fi 뒤 시스템 메모리가 모자라 두 번째부터 `OSError: can't create thread`(직후 `free heap: 52 bytes`)였습니다. 그래서 **감시 스레드 하나만** `startMain`으로 Wi-Fi보다 먼저 띄우고, 명령·텔레메트리·비전 읽기는 `main.py`의 시작 스레드에서 `app.run()` 한 루프로 돕니다. 라이다 J5 중계는 `config.LIDAR_RELAY_ENABLED = False`(기본)로 만들지 않습니다.
같은 부팅 로그에 `QMI8658 init.`이 보여 로봇 A IMU 칩은 QMI8658로 보입니다(순정 펌웨어 출력).
- `main.py`가 이제 돌아오지 않으므로 REPL은 Ctrl+C로 들어갑니다(감시 스레드는 계속 돌며 정지·래치 유지).
- 원래 프로그램이 돌던 상태에서 Ctrl+C 후 `import main`하면 원래 스레드가 메모리를 쥐고 있어 실패합니다. 업로드 뒤에는 **재부팅**으로 실행합니다.

## 3. 원래 시작 파일·복구

- [`firmware/robot/python/device-original/`](../firmware/robot/python/device-original/): 사용자가 제공한 메인 보드 원래 `boot.py`·`main.py`를 `.txt`로 보관(SHA-256·크기는 `manifest.json`).
  - 장치 시작 파일 사본일 뿐, 펌웨어 전체·보정값·카메라 플래시 백업이 아닙니다.
  - **실행·import·자동 업로드 금지.** 원래 main에는 로봇 생성·이동·동작 코드, 문서 범위 밖 인자, 통신 정지 감시 없는 경로가 있습니다. 예제로 재사용하지 않습니다.
  - 복구는 사용자가 대상 보드·버전을 확인한 뒤 확장자를 되돌리는 절차로 따로 검토합니다.
- 굽기·업로드 전 플래시 백업은 하지 않습니다(사용자 결정). 되돌릴 때는 순정·제조사 펌웨어를 다시 굽거나 우리 빌드를 다시 굽습니다.

## 4. 메인 보드 Arduino (`firmware/robot/arduino/`, 예비·유지)

`firmware/robot/python/`을 제조사 공식 MechDog Arduino 라이브러리로 그대로 이식한 판입니다. **이 판을 구우면 순정 MicroPython이 지워집니다.** 되돌리려면 순정 펌웨어를 다시 굽고 2절대로 `.py`를 올립니다.

| 구분 | 파일 | 원본 |
| --- | --- | --- |
| 이식성 코어(벤더·Arduino 비의존, 표준 C++) | `mech_config.h`, `mech_proto.*`, `mech_roles.*`, `mech_core.*`, `mech_clock.h`, `mech_backend.h` | `config.py`, `proto.py`, `roles.py`, `core.py`, 주입 경계 |
| Arduino 글루(ESP32·벤더 의존) | `arduino.ino`(수신·감시·라이다 3태스크+뮤텍스), `motion_mechdog.*`(공식 API·배터리·IMU), `net_link.*`(STA+UDP), `lidar_relay.*`(UART↔TCP), `arduino_clock.h`, `secrets.example.h` | `app.py`·`main.py`, `motion.py`, `comm.py`, `lidar_bridge.py` |

### 4.1 빌드

```bash
set MECHDOG_VENDOR_LIBS=C:\Users\<you>\Documents\Arduino\libraries
python firmware/build.py A --only arduino   # arduino-cli 컴파일만 → build/robot_A/arduino/
python firmware/builder/build_main_arduino.py  # ID 확인 없이 → build/main_arduino/compile/
```

| 대상 | 결과 |
| --- | --- |
| 코어 + net_link + lidar_relay (arduino-cli, `-Wall`) | 통과, 경고 없음 |
| motion_mechdog + .ino (벤더 라이브러리 필요) | **미확인** |
| 실제 로봇 동작 | **실물 미검증** |

- 벤더 라이브러리는 제조사 ESP32 개발 패키지로 사용자 Arduino 라이브러리 폴더에 설치합니다. 저장소에 넣지 않습니다.
- 보드 **ESP32 Dev Module**, ESP32 Arduino 코어 **3.3.12**. 합본·업로드 기능은 빌드 도구에 없습니다.

### 4.2 설정·업로드 (사용자 가이드)

사용자가 그대로 따라 합니다. 에이전트는 빌드(4.1)까지만 하고 이 순서를 안내합니다.

1. `secrets.example.h` → `secrets.h`(커밋 금지): `MECH_WIFI_SSID`, `MECH_WIFI_PASS`, `MECH_ROBOT_ID` ('A'/'B'). 로봇 간 차이는 ID뿐.
2. 받침대에 올리고 USB 연결 → Arduino IDE 업로드.
3. 시리얼 115200: `WiFi OK  id=A  ip=192.168.137.x`. 부팅 후 boot 래치 상태가 정상입니다.

### 4.3 알려진 제약·확인 필요

- **동작 그룹은 실행 중 멈출 수 없음:** 벤더 Arduino `action_run()`은 끝까지 블로킹이고 중단 API가 없습니다. 워커 태스크에서 돌려 수신·감시는 막지 않지만, ESTOP은 그룹이 끝난 뒤에야 실제로 멈춥니다. 현장 기능에 동작 그룹을 쓰지 않습니다.
- 배터리 값 mV 가정 [확인 필요], IMU 기본 꺼짐(`imu_unknown`, 실물 확인 후 `motion_mechdog.cpp`의 `MECH_ENABLE_IMU`), 라이다 UART 방향·`rxbuf` [확인 필요], Wi-Fi 절전 끄기 미지원 시 `warn=pm_on`.
- 해제 거부(`reset_denied`): 배터리 6800 mV 미만, Wi-Fi 불안정, 동작 그룹 실행 중.

## 5. 네트워크 (현재 구성)

Windows 노트북의 모바일 핫스팟(2.4 GHz 고정, WPA2)에 메인 보드와 카메라가 STA로 붙습니다. 노트북은 게이트웨이 `192.168.137.1`, 장치는 `192.168.137.x`. 5 GHz면 두 장치 모두 못 붙습니다. 영상은 메인 보드를 거치지 않고 카메라 → 노트북으로 바로 갑니다.

- 실물 확인: 카메라 v0.1.8 한 대가 핫스팟에 STA로 붙어 640×480 MJPEG를 연속 전송, PC 화면에서 Wi-Fi 영상과 USB LiDAR 동시 표시, 노트북의 기존 인터넷 유지.
- 이전 시험 구성: 제조사 기본 카메라 펌웨어의 개방 AP `HW_ESP32S3CAM`(`192.168.5.1`)에 본체·노트북을 붙이는 방식(`--broadcast` 기본값이 `192.168.5.255`인 이유). 비밀번호가 없으므로 시험할 때만.
- PC 화면: `python -m dashboard.server --robot A --robot-ip <IP|auto> --allow-real --cam http://<카메라>:81/stream [--relay-lidar]` → `http://127.0.0.1:8090`. 자세한 것은 [dashboard.md](dashboard.md).

## 6. 비전 모듈 맞춤 펌웨어 (`firmware/vision/`)

목적: 영상을 Wi-Fi로 노트북에 보내기. **메인 보드에 올리지 않습니다.** 카메라 안 인식(얼굴·색·라인)은 넣지 않았습니다(영상 전송 우선, 같은 칩의 메모리·속도 경쟁). 인식이 필요하면 PC에서 영상으로 합니다.

| 항목 | 제조사 기본 영상 펌웨어 | 맞춤 펌웨어 |
| --- | --- | --- |
| Wi-Fi | AP `HW_ESP32S3CAM`(`192.168.5.1`) | STA 접속, 실패 30초 뒤 점검용 AP `MECHDOG-<ID>-CAM`(기본 비밀번호 `password`, `192.168.5.1`), STA 재시도 계속 |
| 영상 | 웹 화면 | `:81/stream` MJPEG(최신 프레임만, 최대 2 수신자), `:80/capture` JPEG 1장, `:80/status` JSON, USB 시리얼 `frame`(JPEG 1장, 진단용) |
| 이름 | 고정 IP | mDNS `mechdog-a-cam.local` / `mechdog-b-cam.local` |
| 메인 보드 I2C | 응답 없음(errno 19) | 공식 `ESP32S3Cam` 읽기에 **"결과 없음"** 고정 응답(연결 확인 용도) |
| 감시 | — | 작업 워치독 10초, 카메라 재초기화, Wi-Fi 재접속, 10분 고립 시 재부팅 |
| 설정 | — | USB 시리얼 명령으로 NVS 저장. 저장소에 비밀번호 없음 |

HTTP 머리글·I2C 명령표는 [protocol.md](protocol.md).

### 6.1 하드웨어 근거

| 항목 | 값 | 근거 |
| --- | --- | --- |
| 플래시 | 4 MB 설정, DIO, 80 MHz, 합본을 `0x0` | 제조사 기본 펌웨어 이미지 머리글, 제조사 플래시 안내 |
| PSRAM | 옥탈(OPI) | 제조사 펌웨어 빌드 설정 |
| 카메라 핀 | ESP32-S3-EYE 배치(XCLK 15, SIOD 4, SIOC 5, D0~D7 = 11·9·8·10·12·18·17·16, VSYNC 6, HREF 7, PCLK 13, PWDN·RESET 없음), XCLK 15 MHz | 제조사 예제 |
| 센서 | 2 MP. **로봇 A·B 실물 모두 GC2145**(PID 0x2145, JPEG 압축기 없음). 로봇 A: v0.1.9 앱 업데이트 후 I2C 0x53 ok, 핫스팟 STA 접속, `/status`·`/capture` 확인(2026-11-22) | 실물 시리얼·`/status` |
| I2C(메인 쪽) | 슬레이브 SDA IO47, SCL IO48, 100 kHz, 주소 **0x53**(구세대 레지스터형, 기본) / 0x52(신세대 명령형) | 제조사 예제. 로봇 B 실물에서 0x53으로 공식 읽기 `observed`, `read_ms: 2`, errno 19 없음 |
| USB | CH340 USB-시리얼(내장 CDC 아님) | 제조사 안내 |
| 전원 | 5 V 2 A 이상(부족하면 영상 깨짐) | 제조사 안내 |

핀이 실물과 다르면 시리얼에 `camera FAILED`, `/status`의 `camera.ok=false`. 다른 보드 정의로 추측해 바꾸지 말고 결과를 남깁니다. errno 19가 계속되면 `config.h`의 `CAM_I2C_ADDR`를 0x52로 바꿔 빌드해 봅니다.

### 6.2 JPEG 미지원 센서 대응 (v0.1.5~)

- 센서가 JPEG를 거절하면 RGB565로 다시 열고 ESP32-S3에서 JPEG로 변환(코어 포함 최적화 인코더, 실패 시 `frame2jpg`). 출력은 여전히 JPEG.
- 시작 로그 `[cam] sensor <이름> (PID 0x....), software JPEG|sensor JPEG`, `/status.camera.encoder` = `software`/`sensor`. 소프트웨어 모드 품질은 `CAM_SOFT_JPEG_QUALITY`(기본 80).
- v0.1.5는 변환 때문에 loop가 굶어 워치독이 10~20초 뒤 재부팅 → v0.1.6부터 매 주기 최소 `CAM_MIN_YIELD_MS`(30 ms) 쉼.
- `/status.camera.dimensions_measured=true`일 때만 width/height가 실제 프레임 값(v0.1.4~).

로봇 B 실측(640×480, 같은 공유기 Wi-Fi 노트북, RSSI 약 -51~-58, 3분 연속, v0.1.7 기준):

| 항목 | 값 |
| --- | --- |
| 안정성 | 재부팅·워치독·failures·reinits 0 |
| 카메라 내부 생성 / 스트림 수신 | 약 5.9 fps / 약 2.2 fps (최대 간격 1.0초) |
| 프레임 나이 평균 | 약 0.38초 |
| 한 장 크기 | 약 31 KB |
| 내부 여유 메모리 | 약 104 KB (장시간 미확인) |
| 색·방향 | 정상(반전 없음) |

- 초기 목표 [가정]: 수신 10 fps 이상, 수신 나이 p95 300 ms 이하. 현재 실측은 미달(balanced 상한 약 15 fps에도 못 미침). 병목은 Wi-Fi 전송으로 추정(TCP 송신 버퍼 약 5.7 KB × 왕복 지연 ping 평균 30 ms, 최대 138 ms, 미검증). 한 장 크기를 줄이면 수신 fps가 오를 것으로 예상. 화질 기준 결정 필요.
- 본체 배터리 전원의 장시간 스트림, JPEG 센서 카메라에서의 동작은 미측정.

### 6.3 기본값 (`config.h`)

| 값 | 기본 | 상수 |
| --- | --- | --- |
| 프로필 | balanced 640×480, 품질 10, 상한 약 15 fps / detail 800×600, 약 10 fps / PSRAM 없으면 320×240·버퍼 1개 | `--profile` |
| 프레임 버퍼 | PSRAM 2개, 최신 프레임 모드 | — |
| 동시 스트림 | 2 | `CAM_MAX_STREAM_CLIENTS` |
| 촬영 쉬기 | 10초 무요청(이때 fps 0.0 정상) | `CAM_IDLE_MS` |
| 새 프레임 대기 | 스트림 3초(넘으면 연결 닫음), 캡처 1.5초(503) | `CAM_FRAME_WAIT_MS`, `CAM_CAPTURE_WAIT_MS` |
| 재초기화 | 연속 실패 10회, 재초기화 3회 실패 시 재부팅 | `CAM_FAILS_BEFORE_REINIT` |
| 워치독 | 10초 | `CAM_WDT_TIMEOUT_MS` |
| STA 재시도 / AP 전환 | 15초(AP 접속자 있으면 60초) / 30초 | `CAM_STA_RETRY_MS`, `CAM_STA_RETRY_AP_BUSY_MS`, `CAM_STA_FALLBACK_MS` |
| 고립 재부팅 | 10분(SSID 설정 시) | `CAM_NET_RESTART_MS` |
| 점검용 AP 비밀번호 | `password`(v0.1.9~, 약한 값이라 STA 실패 때만 켜짐. 현장에서는 `set ap_pass`로 변경, `set ap_pass`만 쓰면 AP 끔) | `CAM_AP_PASSWORD` |
| 영상 방향 | 센서별 기본 | `CAM_VFLIP`, `CAM_HMIRROR` |

XCLK 15 MHz는 속도를 위해 올리지 않습니다. 원시 RGB/YUV 전송은 하지 않습니다.

### 6.4 빌드

```powershell
python firmware/build.py A --only vision                        # 로봇 A 전용 합본 → build/robot_A/vision/latest/
python firmware/builder/build_vision_cam.py --robot A --verify-release  # 장치·컴파일러 없이 합본·해시·명세·소스·ID 일치 확인
python firmware/builder/build_vision_cam.py --release           # A/B 공통 합본 → build/vision_cam/latest/ (ID는 시리얼)
```

- 도구: Arduino IDE의 `arduino-cli`, ESP32 Arduino 코어 **3.3.12**(ESP-IDF 5.5.x), 같은 패키지 esptool. 다른 위치면 `ARDUINO_CLI`, `ESPTOOL_PATH`.
- FQBN: `esp32:esp32:esp32s3:PSRAM=opi,FlashMode=dio,FlashSize=4M,PartitionScheme=huge_app,CDCOnBoot=default,CPUFreq=240` (앱 3 MB·OTA 없음, 현재 앱 약 1.0 MB).
- `--release`는 `secrets.h`가 있으면 멈추고(배포 이미지에 비밀번호 금지), 이미지 안 소스 경로의 사용자 폴더를 지웁니다. 컴파일·검증이 실패하면 이전 latest를 유지합니다. `release-previous`가 남아 있으면 다음 배포가 중단되며 사람이 확인 후 정리합니다. 빌드와 굽기를 동시에 하지 않습니다.
- 해시는 산출물 변경 확인용이며 서명·실물 검증이 아닙니다. 이전 바이너리는 보관하지 않고 Git 이력으로만 복원합니다.
- 제조사 개발 환경은 코어 2.0.x였고 우리는 3.3.12입니다(카메라 드라이버·SCCB·워치독 설정 방식 차이). 2.0.x 빌드는 확인하지 않았습니다. 공개 라이브러리는 Arduino-ESP32 코어(LGPL-2.1)와 그 안의 ESP-IDF·esp32-camera(Apache-2.0)만.

### 6.5 굽기·설정 (에이전트 수행)

에이전트가 직접 합니다. **[사용자]** 표시 단계만 사용자에게 요청하고 끝날 때까지 기다립니다.

1. **[사용자]** 본체 전원을 끄고 카메라 IIC 케이블을 뺀 뒤, 데이터용 Type-C로 **카메라만** PC에 연결(역급전 미확인에 따른 우리 안전 권고, 제조사 절차 아님). 장치 관리자 `USB-SERIAL CH340` 포트 확인, 메인 보드 포트와 혼동 금지. 포트를 잡은 프로그램은 닫습니다.
   에이전트는 `flash-id`로 ESP32-S3인지 확인한 뒤 진행합니다. 메인 보드(ESP32 클래식) 포트면 즉시 멈춥니다.
2. 합본 해시 확인: `Get-FileHash build\robot_<ID>\vision\latest\mechdog_vision_cam_0x0.bin -Algorithm SHA256` = `.sha256`.
3. 칩 확인: `esptool --chip esp32s3 --port COMx flash-id` (백업은 하지 않음. esptool 4.x는 `flash_id`처럼 밑줄). 시리얼 `show`로 기존 ID·SSID가 있는지 봅니다.
4. 굽기: `esptool --chip esp32s3 --port COMx --baud 460800 write-flash 0x0 build\robot_<ID>\vision\latest\mechdog_vision_cam_0x0.bin`. 0x0 합본은 저장 설정을 지우므로 카메라 ID가 빌드 ID로 시작합니다. 제조사 플래시 도구를 쓰면 ESP32-S3 / 0x0000 / 80MHz / DIO / 460800, **ERASE 누르지 않음**. 쓰는 중 케이블·전원 분리 금지.
   - 업데이트(설정 유지): 같은 맞춤 펌웨어가 있는 카메라는 앱만 `write-flash 0x10000 build\robot_<ID>\vision\compile\vision.ino.bin`(저장된 ID·Wi-Fi 유지). 0x0 합본은 NVS를 지울 수 있으므로 굽고 나서 설정을 다시 입력합니다.
   - Arduino IDE로 올릴 때: `firmware/vision/vision.ino`를 폴더째 열고 Board ESP32S3 Dev Module, PSRAM OPI, Flash Mode DIO 80MHz, Flash Size 4MB, Partition Huge APP, CPU 240MHz, USB CDC On Boot Disabled, Erase All Flash Disabled. 합본 bin을 스케치로 열지 않습니다.
5. 설정: 시리얼 115200, 줄 끝 Newline. `set robot <ID>`, `set ssid <SSID>`, `set pass <비밀번호>`, (선택) `set ap_pass <8자 이상>`, `set key <키>`, `show`, `reboot`.
   - Wi-Fi 비밀번호는 에이전트가 Windows(`netsh wlan show profile name=<SSID> key=clear`, 모바일 핫스팟 설정)에서 얻어 시리얼로만 보냅니다. 출력·로그·파일·커밋에 남기지 않습니다([rules.md](rules.md) 4.1절).
   - `show`는 비밀값을 가림. `clear <항목>`은 빌드 기본값으로, `set key`(값 없음)는 빈 값 저장 → 키·AP 꺼짐. 키는 영문·숫자·`. _ ~ -`만.
   - 시리얼 값이 `secrets.h` 빌드 값보다 우선. 카메라 ID는 그 카메라가 달린 로봇의 ID.
   - 비밀번호는 장치에만 입력하고 저장소·이슈·채팅에 적지 않습니다.
6. 확인: 10초마다 `sta <IP> rssi -55 | cam 1 fps 0.0 clients 0` 줄. `/status`에 `"robot":"<ID>"`, `camera.ok=true`, `wifi.mode=sta`, `camera.psram=true`. `/capture`, `:81/stream`. `.local`이 안 되면(Windows mDNS 불안정) 시리얼의 IP 사용. 키를 설정했으면 `?key=<키>`, 없으면 401.
7. **[사용자]** 본체 연결: 본체 전원 끈 상태에서 IIC 케이블을 **본체 물리 IIC 포트 1**에 복원(Python에서는 `Hiwonder_IIC.IIC(2)`). 메인 보드의 공식 `ESP32S3Cam` 읽기는 `observed`, `has_result=False`(결과 없음 고정 응답)가 정상입니다.

- 끝나면 에이전트가 채팅으로 알립니다: 로봇 ID, SSID, 펌웨어 버전, IP, 점검용 AP 비밀번호, 확인 결과(비밀번호 제외).
- 접근 키는 HTTPS가 아니므로 같은 망 도청에는 보호가 되지 않습니다. 망 자체를 WPA2, 외부와 분리. 핫스팟/공유기에서 DHCP 예약을 권장.
- 영상·사진은 저장하거나 이슈에 붙이지 않고 숫자(fps, `frame_age_ms`, RSSI)만 남깁니다.

### 6.6 복구 (에이전트 수행)

6.5절처럼 물리 조작만 사용자에게 요청하고 에이전트가 굽습니다.

- 우리 합본을 0x0에 다시 굽고 6.5절 5번 설정을 다시 합니다.
- 또는 제조사 기본 영상 전송 바이너리를 같은 설정(ESP32-S3, 0x0000, 80MHz, DIO, 460800)으로 → AP `HW_ESP32S3CAM` 방식으로 돌아감.
- 제조사 배포에는 기능별(얼굴·색·라인) 카메라 바이너리가 따로 있습니다. 한 펌웨어에서 영상 전송과 모든 인식이 된다고 가정하지 않고, 다른 확장 모듈·플랫폼용 펌웨어를 올리지 않습니다. 버튼(다운로드 모드) 조합은 추측하지 않습니다.
- 출력이 없거나 계속 재시작하면 로그 몇 줄(비밀번호 제외)을 남기고 복구합니다.

### 6.7 확인하지 못한 것

장시간 동작·발열·메모리, 본체 전원으로 카메라+Wi-Fi 동시 구동 시 전원 여유, 카메라 두 대 동시 전송, Wire 슬레이브 실제 타이밍, 코어 2.0.x 빌드.
