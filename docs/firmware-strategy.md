# 펌웨어 방침

로봇 한 대에는 프로그램이 올라가는 칩이 **두 개** 있습니다. 칩마다 개발 방식과 폴더를 정해 둡니다.

| 칩 | 위치 | 개발 방식 | 폴더 |
| --- | --- | --- | --- |
| **메인 보드** ESP32(클래식) | 몸통 안 | **1순위 MicroPython(Hiwonder 공식 Python API)**, 예비 Arduino | `robot/`, `custom_sensors/` (Python) / `firmware/main_arduino/` (Arduino, 나중) |
| **비전 모듈** ESP32-S3 | 로봇 앞쪽 카메라 | **Arduino(C++)**, Arduino IDE로 빌드·업로드 | `firmware/vision_cam/` |

## 1. 메인 보드: Python 우선, Arduino는 예비

### 1.1 선택지와 결정

제조사가 메인 보드 개발 방식으로 제공하는 것은 세 가지입니다.

| 방식 | 도구 | 결정 |
| --- | --- | --- |
| MicroPython | Hiwonder Python Editor, 순정 펌웨어(MicroPython v1.21.0) | **주 개발 방식** |
| Arduino(C++) | Arduino IDE + 제조사 Arduino 라이브러리(`HW_MechDog`, `Hiwonder`) | **예비 펌웨어** — Python 구현을 옮겨 나중에 만든다 |
| Scratch | 제조사 블록 코딩 도구 | 쓰지 않음 |

### 1.2 순서

1. **Python 먼저 완성:** `robot/`(통신·안전·동작)과 `custom_sensors/`(라이다 중계)를 순정 MicroPython 펌웨어 위에서 만듭니다.
   펌웨어를 다시 굽지 않고 `main.py`만 올리므로 되돌리기 쉽고, 제조사 공식 Python API를 그대로 씁니다([MechDog 제어 API 규칙](dev/mechdog-api.md)).
2. **실물 검증:** 사용자가 승인한 범위에서 실제 로봇으로 통신·정지·라이다 중계·걸음을 확인합니다.
3. **Arduino로 리팩토링:** Python 구현이 안정되면, 같은 동작을 제조사 Arduino 라이브러리로 옮겨 `firmware/main_arduino/`에 예비 펌웨어로 둡니다.
   MicroPython의 성능·메모리 한계(예: 고속 UART 중계, 감시 타이머 지연)가 실측으로 문제가 될 때 바꿔 쓸 수 있게 하는 것이 목적입니다.

### 1.3 두 펌웨어가 지켜야 할 것

- **같은 통신 규약:** [`docs/protocol.md`](protocol.md)의 `CMD|...|$` / `TEL|...|$` 메시지, 포트, 라이다 TCP 원시 중계를 그대로 따릅니다.
  Pi 5 쪽(`host/`)은 어느 펌웨어인지 몰라도 동작해야 합니다.
- **같은 안전 동작:** 명령 600ms 끊김 시 정지·래치, ESTOP 최우선, RESET 후 텔레메트리로 해제 확인, 저전압 정지, 범위 밖 값 자르기.
- **같은 제어 수단:** Arduino 판도 제조사 Arduino 라이브러리의 공식 동작 함수(이동·자세·동작 그룹·균형)만 쓰고, 서보를 직접 구동하지 않습니다.
- **테스트:** Python 판은 `tests/`의 가짜 모듈 테스트, Arduino 판은 `arduino-cli` 컴파일 확인과 같은 시나리오의 검증표로 확인합니다.

### 1.4 펌웨어 전환 주의

- Arduino 판을 올리면 메인 보드의 순정 MicroPython 펌웨어가 지워집니다. **굽는 일은 사용자만** 하고, 굽기 전에 현재 플래시 전체를 백업합니다.
- Python 판으로 돌아가려면 제조사 순정 펌웨어를 다시 구운 뒤 `main.py`를 올립니다. 절차는 Arduino 판을 만들 때 문서로 함께 남깁니다.

## 2. 비전 모듈(ESP32-S3): Arduino

- 제조사 비전 모듈 예제와 같은 Arduino(C++) 방식으로 `firmware/vision_cam/`에 맞춤 펌웨어를 만듭니다.
- 목적: Pi 핫스팟 로봇망 접속(STA, 전용 공유기는 예비), 지연이 적은 MJPEG 영상·한 장 캡처·상태 확인, 메인 보드 `robot/vision.py`가 쓰는 I2C 인터페이스(주소 0x53) 호환 유지.
- 빌드: Arduino IDE와 같은 빌드 엔진(`arduino-cli`)으로 컴파일을 확인합니다. ESP32 코어는 설치된 3.3.12 기준을 우선합니다.
- 굽기: **사용자만** 합니다. 굽기 전 현재 플래시 백업(esptool), 문제 시 백업 또는 제조사 기본 영상 전송 펌웨어로 복구합니다.
  자세한 절차는 `docs/vision-cam-firmware.md`에 둡니다.

## 3. 요약

| 순서 | 대상 | 방식 | 상태 |
| --- | --- | --- | --- |
| 1 | 메인 보드 | MicroPython (`robot/`, `custom_sensors/`) | 진행 중 — 주 펌웨어 |
| 2 | 비전 모듈 | Arduino (`firmware/vision_cam/`) | v0.1.4 화질·전송 조정, 최신 build 산출물만 유지, 실물 미검증 ([안내](vision-cam-firmware.md)) |
| 3 | 메인 보드 | Arduino (`firmware/main_arduino/`) | [설계·최소 컴파일 골격](../firmware/main_arduino/README.md)만 준비. 구동 API 중단/완료 대응 미확인, Python 실물 검증 후 이식 |
