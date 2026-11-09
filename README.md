# Mechdog Industry Safety

MechDog 사족보행 로봇을 활용한 산업 현장 안전 프로젝트입니다.

## 시연 시나리오

로봇 2대가 현장을 지키다가 카메라로 쓰러진 사람을 발견하면 대시보드로 관리자에게 알리고,
그중 1대가 관리자 위치(사무실 등)로 가서 관리자를 사고 지점까지 안내해 조치하게 합니다.
→ [docs/demo-scenario.md](docs/demo-scenario.md)

## 지금 시작하는 순서

**카메라 확인 완료(사용자 실측):** 구입 당시 영상 전송 펌웨어에서 휴대폰을 `HW_ESP32S3CAM`에 연결하고
`http://192.168.5.1/` → **Image**로 실시간 영상 표시를 확인했습니다. 현재 펌웨어를 유지합니다.
얼굴 IIC API는 오류 19로 미확인 상태이며, 영상 성공이 낙상 감지·PC/Pi 수신 검증을 뜻하지는 않습니다.
카메라만 확인했으며 로봇 모션은 시험하지 않았습니다.

**현재 보유: MechDog 본체와 장착된 ESP32-S3 비전 모듈. Pi 5·라이다·추가 부품은 도착 대기입니다.**
지금은 [본체·카메라 우선 점검](docs/user-tests/current-hardware.md)을 먼저 수행합니다.
카메라 인식 읽기 오류가 나면 [사용자용 비전 펌웨어 확인·업로드 가이드](docs/vision-firmware.md)를 따릅니다.
현재 실물 작업은 비전만 허용되어 있으며, 펌웨어 업로드와 전원 조작은 사용자가 직접 수행합니다.
부품 도착 예정은 약 일주일 뒤이며 확정 수령일은 아닙니다. [단계별 적용 계획](docs/hardware-rollout.md)을 따릅니다.

실제 MechDog는 준비되어 있습니다. 아래 순서로 사용자 확인과 자동 개발을 나눕니다.
PC 테스트 통과는 장치 검증 완료를 뜻하지 않습니다.

1. **PC에서 자동 테스트:** `python -m unittest discover -s tests`. 실제 로봇 없이 합성 데이터와 가짜 모듈로 실행합니다.
2. **Pi 5 준비:** [호스트 설치](docs/host-setup.md)의 Ubuntu 24.04 arm64·ROS 2 Jazzy 절차를 따릅니다.
3. **사용자 실물 확인:** [사용자 테스트 안내](docs/user-tests/README.md)에서 A·B별 체크리스트와 결과 양식을 확인합니다.
   먼저 읽기 확인·UART·전원·Wi-Fi·카메라부터 수행합니다. 실행 대상과 핀을 모르면 연결하지 않습니다.
4. **구동 시험:** 읽기 확인 결과를 검토한 뒤, 대상 로봇과 실행 범위를 별도로 승인하고 진행합니다.
   기존 장치 `main.py`를 보존하고 전원 차단 수단과 지지 장치를 준비합니다.

## 펌웨어 방침

- **메인 보드(ESP32):** MicroPython(Hiwonder 공식 Python API)을 먼저 개발하는 주 펌웨어로 쓰고, 검증 후 같은 동작을 Arduino로 옮겨 예비 펌웨어로 둡니다. Scratch는 쓰지 않습니다.
- **비전 모듈(ESP32-S3):** Arduino IDE로 개발합니다.
- 자세한 순서와 규칙: [펌웨어 방침](docs/firmware-strategy.md)

## 파일과 실행 위치

| 경로 | 실행 위치 / 용도 | 사용자 행동 |
| --- | --- | --- |
| `host/` | PC·Pi 5의 수신·판단 로직 | 장치에 업로드하지 않음 |
| `ros2/` | Pi 5의 ROS 메시지 어댑터 | 해당 설치 안내에 따라 실행 |
| `robot/` | MechDog 메인 보드의 MicroPython 펌웨어 (주 펌웨어) | 업로드·실행 전 대상별 승인, 기존 main.py 백업 |
| `firmware/vision_cam/` | 앞쪽 ESP32-S3 비전 모듈용 Arduino 펌웨어(영상 → Pi 5) | [설치·Wi-Fi 설정 안내](docs/vision-cam-firmware.md)대로 사용자가 굽기, 굽기 전 플래시 백업 |
| `firmware/main_arduino/` | 메인 보드용 Arduino 예비 펌웨어 (Python 판 검증 후 작성 예정) | 굽기 전 플래시 백업, 순정 MicroPython 복구 절차 확인 |
| `custom_sensors/` | 로봇의 추가 라이다 중계 | robot 파일과 함께 장치 최상위에 배치하는 구조 |
| `tools/bringup/` | 파일별로 PC/Pi 또는 로봇 REPL에서 실행 | [실물 확인 절차](docs/bringup.md)의 실행 위치 확인 |
| `tools/mock/`, `tests/` | PC에서만 실행하는 합성 서버·가짜 모듈 | 로봇에 업로드하지 않음 |
| `docs/user-tests/` | 사용자 전용 체크리스트·빈 결과 양식 | 결과를 GitHub 실물 확인 이슈에 기록 |
| `scenario/`, `dashboard/` | 호스트의 시연 흐름·관리자 화면 | 개발 상태와 모의/실물 연결 모드를 먼저 확인 |

`robot/`은 MechDog **메인 보드용**입니다. 앞쪽 ESP32-S3 카메라에 이 펌웨어를 올리지 않습니다.
Wi-Fi 자격 정보는 장치의 로컬 `secrets.py`에만 작성하고 GitHub에는 올리지 않습니다.
실제 사람 영상·얼굴·Wi-Fi 비밀번호·장치 식별번호는 결과에 첨부하지 않습니다.

MQTT는 기존 CMD/TEL 내용과 안전 감시를 유지하는 선택형 통신 계층으로 검토합니다.
현재 배포 경로는 UDP 명령·상태와 TCP 라이다 중계입니다. MQTT 사용 여부는 구현·검증 상태를 확인한 뒤 선택합니다.

카메라는 `robot/vision.py`에서 **Hiwonder Python `ESP32S3Cam(IIC(2))`**으로 연결하며,
로봇 앱의 별도 읽기 루프에서 관측합니다. 기본 얼굴 결과는 낙상 감지나 원본 영상 전송 기능이 아닙니다.
현재 `vision_status`는 로봇 내부 진단 값이며 기존 TEL에 새로운 필드를 임의로 추가하지 않습니다.

## 하드웨어 구성

로봇 2대(로봇 A·B)는 같은 구성입니다. 자세한 근거·배선·전원 검토는 [라이다 연동 설계](docs/lidar-integration.md),
제어 규칙은 [MechDog 제어 API 규칙](docs/dev/mechdog-api.md)을 봅니다.

```text
 로봇 A·B (각각)                                          고정 위치
 ┌───────────────────────────────────────┐
 │ 앞쪽 ESP32-S3 비전 모듈 ── 영상(Wi-Fi) ─┼──┐
 │ 등 위 RPLIDAR A1M8-R6                  │  │   ┌──────────────────────┐
 │   └ UART ─▶ J5(IO32/IO33)              │  ├──▶│ Raspberry Pi 5 16GB  │
 │ 메인 ESP32 (MicroPython, 공식 API)      │  │   │ 지도·위치·경로,       │
 │   ├ 라이다 원시 중계(TCP) ─────────────┼──┤   │ 쓰러진 사람 감지,     │
 │   └ 명령 수신·상태 보고(UDP) ◀─────────┼──┘   │ 대시보드             │
 └───────────────────────────────────────┘      └──────────────────────┘
                     전용 공유기(Wi-Fi)
```

### 로봇: Hiwonder MechDog × 2

| 항목 | 내용 |
| --- | --- |
| 몸체 | 사족보행 다리 4개 |
| 메인 보드 | ESP32(클래식, ESP32-S3 아님), 제조사 순정 MicroPython 펌웨어 그대로 사용 |
| 제어 | **Hiwonder 공식 Python API**(`HW_MechDog`, `Hiwonder`, `Hiwonder_IIC`)만 사용 |
| 팔·집게·부가 서보 | 없음. 부가 서보 9·10번 미사용 |
| 추가 센서 | 비공식 센서 장착 예정 — [배선 표](docs/dev/mechdog-api.md#63-배선-기록) |

### 비전 모듈: ESP32-S3 카메라 (로봇 앞쪽)

- 영상을 Wi-Fi로 Pi 5에 보내고, Pi 5가 쓰러진 사람을 감지합니다.
- 전용 공유기에 붙어 두 대 영상을 동시에 보내는 **맞춤 펌웨어**를 준비했습니다(실물 미검증):
  [설치·Wi-Fi 설정 안내](docs/vision-cam-firmware.md), 바로 굽는 이미지 `firmware/vision_cam/release/`.
- 5V 2A 이상 전원이 필요합니다.

### 라이다: [SLAMTEC] 슬램텍 RPLIDAR A1M8-R6 360도 거리측정 라이다 센서 - 12m

로봇마다 1대, 등 위에 테이프로 고정합니다(시연 전 고정 상태와 정면 0° 방향 확인).

| 항목 | 값 (공개 데이터시트 기준) |
| --- | --- |
| 측정 | 360° 2D, 거리 0.15~12 m |
| 측정 속도 | 초당 8000회 이상 |
| 회전 | 5V 모터에서 약 5.5 Hz(한 바퀴 약 1450점). 5.5~10 Hz로 올리려면 모터에 9V 별도 공급 |
| 통신 | UART 3.3V TTL, 115200 bps, 8N1 |
| 전원 | 측정 코어 5V 동작 300~350 mA(켜질 때 최대 600 mA) + 모터 5V 약 100 mA |

**MechDog 연결** ([라이다 연동 설계](docs/lidar-integration.md) 4절)

| 라이다 | MechDog GPIO 포트 J5 | 비고 |
| --- | --- | --- |
| TX | J5-4 IO32 (로봇 RX) | 방향은 제조사 예제로 확인(첫 연결에서 응답으로 재확인) |
| RX | J5-3 IO33 (로봇 TX) | 직렬 저항 넣지 않음 |
| GND | J5-2 GND | 별도 전원 GND와 공통 |
| 전원(코어·모터) | J5-1(5V) 쓰지 않음 | 1단계는 별도 5V 전원, 모터 제어선은 5V에 묶어 항상 회전 |

로봇은 라이다 바이트를 해석하지 않고 Wi-Fi(TCP 20108)로 Pi 5에 그대로 넘깁니다
([통신 규약](docs/protocol.md) 7절).

### 처리 컴퓨터: Raspberry Pi 5 16GB (고정 위치)

- 로봇에 싣지 않고 고정 위치에 둡니다. 부족하면 Jetson Orin Nano Super로 바꿉니다.
- 로봇과는 시연 전용 공유기의 Wi-Fi로 통신합니다. 명령·상태는 UDP 9100/9101, 라이다는 TCP 20108([통신 규약](docs/protocol.md)).
- 기본 환경은 Ubuntu Server 24.04 LTS arm64·ROS 2 Jazzy·Python 3.12입니다. [설치 절차](docs/host-setup.md)를 따릅니다.

> 프로젝트 목표와 실행 방법은 아직 정리 중입니다.

## 개발 규칙

- [docs/README.md](docs/README.md): 브랜치·이슈·코드 리뷰·AI 작업 규칙
- AI 에이전트: [AGENTS.md](AGENTS.md), [CLAUDE.md](CLAUDE.md)
