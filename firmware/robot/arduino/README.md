# 메인 ESP32 Arduino 펌웨어

로봇 메인 보드(ESP32 클래식)에 올리는 **Arduino(C++) 펌웨어**입니다. [`../python/`](../python/) 의 MicroPython 판(app·core·comm·
lidar_bridge 등)을 제조사 공식 MechDog Arduino 라이브러리로 **그대로 이식**한 것으로, 같은 통신 규약·안전 동작을
지킵니다([ai/protocol.md](../../../ai/protocol.md), [ai/firmware.md](../../../ai/firmware.md)).
세팅·업로드는 [ai/firmware.md](../../../ai/firmware.md) 4절을 따릅니다.

> **업로드(굽기)는 사용자만** 합니다([ai/firmware.md](../../../ai/firmware.md) 4.2절). 이 .ino 를 올리면 메인 보드의 순정 MicroPython 이
> 지워집니다. 굽기 전 현재 플래시 전체를 백업하고, 되돌리려면 순정 펌웨어를 다시 굽고 `main.py` 를 올립니다.

## 파일 구성

**이식성 코어 — 벤더·Arduino 비의존(안전 로직), 표준 C++:**

| 파일 | Python 원본 | 내용 |
| --- | --- | --- |
| `mech_config.h` | `python/config.py` | 포트·임계값·동작 시간 |
| `mech_proto.{h,cpp}` | `python/proto.py` | 명령 메시지 해석(파싱·범위 자르기) |
| `mech_roles.{h,cpp}` | `python/roles.py` | 임대 역할 |
| `mech_core.{h,cpp}` | `python/core.py` | 명령 처리·감시·래치·저전압·텔레메트리 상태기계 |
| `mech_clock.h`, `mech_backend.h` | (주입 경계) | 시계·모션·센서 추상 인터페이스 |

**Arduino 글루 — ESP32·벤더 의존(컴파일 검증만):**

| 파일 | Python 원본 | 내용 |
| --- | --- | --- |
| `arduino.ino` | `python/app.py`·`main.py` | 세 태스크(수신·감시·라이다) + 뮤텍스로 직렬화 |
| `motion_mechdog.{h,cpp}` | `python/motion.py` + 하드웨어 | 공식 MechDog API 백엔드, 배터리·IMU 읽기 |
| `net_link.{h,cpp}` | `python/comm.py` | Wi-Fi STA + 명령·텔레메트리 UDP |
| `lidar_relay.{h,cpp}` | `python/lidar_bridge.py` | 라이다 UART ↔ TCP 원시 중계 |
| `arduino_clock.h` | — | `millis()` 기반 시계 |
| `secrets.example.h` | `python/secrets.example.py` | Wi-Fi·ROBOT_ID (실제 값은 `secrets.h`, 커밋 금지) |

## 빌드(컴파일만)

벤더 라이브러리(HW_MechDog 등)는 저장소에 넣지 않습니다. 제조사 ESP32 개발 패키지로 Arduino 에 설치해야 컴파일됩니다.
ESP32 Arduino 코어는 **3.3.12** 기준입니다.

```bash
# (선택) 벤더 라이브러리 폴더를 알려 줍니다. 안 주면 Arduino 기본 사용자 라이브러리에서 찾습니다.
set MECHDOG_VENDOR_LIBS=C:\Users\<you>\Documents\Arduino\libraries
python ai/tools/build_main_arduino.py
```

또는 Arduino IDE 에서 `firmware/robot/arduino/arduino.ino` 를 열어 보드 `ESP32 Dev Module` 로 컴파일합니다.
빌드 산출물은 Git 에서 제외되는 `build/` 에만 생깁니다. 합본·업로드 기능은 이 도구에 없습니다.

## 설정

1. `secrets.example.h` 를 `secrets.h` 로 복사하고 핫스팟 SSID·비밀번호, `MECH_ROBOT_ID`('A'/'B')를 채웁니다. `secrets.h` 는 커밋하지 않습니다.
2. 로봇 A·B 는 `MECH_ROBOT_ID` 만 다릅니다. 임계값은 `mech_config.h`(= `python/config.py` 와 같은 값)에서 바꿉니다.

## 검증 상태

| 대상 | 방법 | 결과 |
| --- | --- | --- |
| 코어 + net_link + lidar_relay | arduino-cli 컴파일(ESP32, `-Wall`) | 통과(오류·경고 없음) |
| motion_mechdog + .ino(벤더 의존) | 사용자 Arduino IDE 컴파일 | **미확인 — 벤더 라이브러리 필요** |
| 실제 로봇 동작 | 사용자 업로드·관찰 | **실물 미검증** |

## 알려진 제약 · 실물 확인 필요 항목

- **동작 그룹은 실행 중 멈출 수 없습니다.** 벤더 `action_run()` 은 끝까지 블로킹이고 중단 API(`stop_action`)가 없습니다.
  전용 워커 태스크에서 돌려 수신·감시를 막지는 않지만, 동작 그룹 중 `ESTOP` 은 그룹이 끝난 뒤에야 실제로 멈춥니다
  (규약 3.3절: 래치해도 최대 시간 전 RESET 금지). 현장 기능에는 동작 그룹을 쓰지 않습니다(허용 목록은 대기·신호용).
- **배터리 단위 [확인 필요]:** `readBattery()` 값을 mV 로 가정합니다. 실물에서 전압과 대조해 `mech_config.h` 임계값을 맞춥니다.
- **IMU 기본 꺼짐:** 초기화·축 대응을 확인하기 전에는 기울기를 `imu_unknown`(안전)으로 보냅니다.
  실물 확인 후 `motion_mechdog.cpp` 의 `MECH_ENABLE_IMU` 로 켭니다.
- **라이다 UART 방향·`rxbuf` [확인 필요]**, **Wi-Fi 절전 끄기(PM_NONE) 지원 여부**(안 되면 `warn=pm_on`).
