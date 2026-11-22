# 로봇 Arduino 펌웨어 · 카메라 · 핫스팟 세팅 가이드

운영자 한 명이 **Windows 노트북 1대 + MechDog 1대 + 앞쪽 카메라(ESP32-S3) 1대**를 맡습니다. 두 운영자(로봇 A·B)가
각자 같은 방식으로 세팅합니다. 이 문서 하나로 **네트워크(핫스팟) → 로봇 펌웨어 → 카메라 펌웨어 → 콘솔 확인**까지
처음부터 끝까지 합니다.

- 로봇 메인 보드 펌웨어는 **Arduino 판**([firmware/main_arduino](../firmware/main_arduino/README.md))입니다. `robot/` MicroPython 판을
  제조사 공식 MechDog Arduino 라이브러리로 이식한 것이고, 같은 통신 규약([docs/protocol.md](protocol.md))을 씁니다.
- 카메라 펌웨어는 **맞춤 영상 펌웨어**([firmware/vision_cam](../firmware/vision_cam/README.md), [docs/vision-cam-firmware.md](vision-cam-firmware.md))로, 이미 로봇에 올라가 있습니다.
  이 가이드에서는 **핫스팟에 붙도록 설정**만 하고 다시 굽지 않습니다.
- 펌웨어를 **굽는 일(업로드)은 사용자만** 합니다. 실제 로봇을 움직이기 전에 받침대에 올리고 사용자 확인 범위에서만 합니다.

> 표기: **[확인 필요]** 는 실물에서 확인해야 하는 값입니다. 임계값(배터리·타임아웃)은 실측 전 가정값입니다.

## 0. 토폴로지 — 한 네트워크로 모으기

```text
  [Windows 노트북] --- 모바일 핫스팟(공통 로봇망, 2.4GHz, WPA2) ---+
        │  콘솔(server.py) + 브라우저                              │
        │                                                         ├── [로봇 메인보드 ESP32]  UDP 9100/9101, 라이다 TCP 20108
        └─────────────────────────────────────────────────────────┤
                                                                   └── [카메라 ESP32-S3]      HTTP :81/stream, /status
```

세 장치(노트북·로봇·카메라)가 **같은 핫스팟**에 붙습니다. 노트북이 로봇에 UDP 로 명령·상태를, 카메라에서 HTTP 로 영상을
받습니다. 로봇과 카메라는 모두 2.4GHz 전용이므로 핫스팟을 **2.4GHz** 로 띄웁니다.

## 1. 준비물

- Windows 11 노트북(운영자마다 1대), MechDog 1대, 앞쪽 ESP32-S3 카메라 1대, 등 위 RPLIDAR A1M8.
- USB 케이블(메인 보드 업로드용), Arduino IDE, 제조사 ESP32 개발 패키지(공식 MechDog Arduino 라이브러리 포함).
- 받침대(로봇을 공중에 띄워 바퀴·다리가 바닥에 닿지 않게). 첫 시험은 반드시 받침대에서.

## 2. 네트워크: Windows 모바일 핫스팟(공통 로봇망)

인터넷을 유지하면서 로봇망을 만드는 자세한 경로는 [host-setup.md](host-setup.md#인터넷을-유지하는-로봇망)에 있습니다. 요약:

1. **설정 → 네트워크 및 인터넷 → 모바일 핫스팟** 을 켭니다.
2. **편집** 에서 네트워크 이름(SSID)과 **비밀번호(WPA2, 8자 이상)** 를 정합니다. 예: SSID `mechdog-net`.
3. **대역(Band)을 2.4GHz** 로 고정합니다. 5GHz 면 로봇·카메라가 못 붙습니다.
4. 핫스팟이 켜진 SSID·비밀번호를 로봇 `secrets.h` 와 카메라 설정에 **똑같이** 넣습니다(아래 3·4절).
5. 노트북은 이 핫스팟을 **쓰는 주체이자 제공자**입니다. 노트북 자신은 핫스팟에 "연결"하지 않아도 같은 네트워크(기본 게이트웨이 `192.168.137.1`)에 있습니다.
   로봇·카메라가 받는 IP(`192.168.137.x`)를 확인해 둡니다.

> 운영자마다 **자기 핫스팟 1개**를 씁니다. 두 로봇을 한 핫스팟에 넣어 동시에 쓰는 구성은 별도 실물 시험입니다.

## 3. 로봇 메인보드 Arduino 펌웨어 (각각 따로)

### 3.1 Arduino IDE · ESP32 코어 3.3.12

- [Arduino IDE](https://www.arduino.cc/en/software) 설치 후, **보드 매니저**에서 `esp32`(Espressif)를 설치합니다. 코어는 **3.3.12** 기준입니다.
- 보드: **ESP32 Dev Module**(클래식 ESP32). 포트는 메인 보드가 연결된 COM 포트.

### 3.2 제조사 벤더 라이브러리 설치

- 제조사 ESP32 개발 패키지를 설치해 **공식 MechDog Arduino 라이브러리**(`HW_MechDog` 등)를 Arduino 라이브러리 폴더에 넣습니다.
  이 라이브러리는 저장소에 포함돼 있지 않습니다(제조사 자료). 설치 위치는 보통 `문서\Arduino\libraries\` 입니다.

### 3.3 `secrets.h` 만들기

`firmware/main_arduino/secrets.example.h` 를 같은 폴더의 **`secrets.h`** 로 복사하고 채웁니다(`secrets.h` 는 커밋 금지, `.gitignore` 처리됨).

```cpp
#define MECH_WIFI_SSID "mechdog-net"      // 2절 핫스팟 SSID 와 동일
#define MECH_WIFI_PASS "<핫스팟 비밀번호>"
#define MECH_ROBOT_ID  'A'                // 로봇 A 는 'A', 로봇 B 는 'B'
```

### 3.4 컴파일 확인

```bash
set MECHDOG_VENDOR_LIBS=C:\Users\<you>\Documents\Arduino\libraries
python tools/build_main_arduino.py
```

또는 Arduino IDE 에서 `firmware/main_arduino/main_arduino.ino` 를 열어 **검증(컴파일)** 합니다. 오류가 없으면 다음 단계로.

### 3.5 업로드 (사용자만) · 순정 백업과 복구

> 이 펌웨어를 올리면 메인 보드의 **순정 MicroPython 이 지워집니다.** 되돌리려면 순정 펌웨어를 다시 굽고 `main.py` 를 올려야 합니다
> ([robot-upload.md](robot-upload.md)). **굽기 전 현재 플래시 전체를 백업**합니다(esptool).

1. 로봇을 **받침대**에 올리고 전원을 켠 뒤 USB 로 연결합니다.
2. (권장) 현재 플래시를 백업합니다: `esptool.py --port COM<n> read_flash 0 ALL main_backup.bin`.
3. Arduino IDE 에서 **업로드**(→) 합니다. 완료되면 보드가 재시작합니다.

### 3.6 부팅 확인 (시리얼)

- 시리얼 모니터를 **115200bps** 로 엽니다. Wi-Fi 에 붙으면 `WiFi OK  id=A  ip=192.168.137.x` 가 한 줄 찍힙니다. 이 IP 를 콘솔에서 씁니다.
- 로봇은 켜지면 **잠금(boot) 상태**로 시작해 사람이 해제하기 전까지 움직이지 않습니다(규약 5.1절). 정상입니다.

## 4. 카메라(비전 모듈) 펌웨어 (각각 따로)

카메라 펌웨어는 이미 올라가 있습니다. **핫스팟에 붙도록 설정만** 합니다(다시 굽지 않음). 자세한 절차는 [camera-setup.md](../test_PC/camera-setup.md), [vision-cam-firmware.md](vision-cam-firmware.md).

1. 카메라를 USB 로 연결하고 설정 시리얼을 **115200bps, Newline** 으로 엽니다.
2. 다음을 입력합니다(로봇 ID 를 본체와 맞춤):

   ```text
   set robot A          (로봇 B 면 B)
   set ssid mechdog-net (2절 핫스팟 SSID)
   set pass <핫스팟 비밀번호>
   reboot
   ```

   (또는 `firmware/vision_cam/secrets.h` 의 `CAM_WIFI_SSID`·`CAM_WIFI_PASSWORD`·`CAM_ROBOT_ID` 를 채워 다시 빌드·굽기 — 사용자만.)
3. 브라우저에서 `http://mechdog-a-cam.local/status`(B 는 `mechdog-b-cam.local`)로 로봇 ID·카메라 상태를 확인하고,
   `/capture` 한 장, `:81/stream` MJPEG 를 확인합니다. `.local` 이 안 되면 시리얼 상태 줄의 IP 를 씁니다.

> 카메라 영상 경로는 로봇 메인 보드를 거치지 않고 **카메라 → 핫스팟 → 노트북** 으로 바로 갑니다(규약 11절).

## 5. 설정값 한눈에

| 항목 | 값 | 어디에 |
| --- | --- | --- |
| 공통망 SSID/비밀번호 | 핫스팟과 동일 | 로봇 `secrets.h`, 카메라 설정 |
| 로봇 ID | `A` / `B` | 로봇 `secrets.h`(`MECH_ROBOT_ID`), 카메라 `set robot` |
| 명령/텔레메트리 UDP | 9100 / 9101 | `mech_config.h`(= `robot/config.py`), 콘솔 공용 |
| 라이다 TCP | 20108 | 〃 |
| 카메라 영상 | `:81/stream`, `/status` | 카메라 펌웨어 |
| 통신 끊김·이동 유효시간 | 600 ms [가정] | `mech_config.h` |
| 저전압 경고/래치/해제 | 7000 / 6600 / 6800 mV [가정] | `mech_config.h` |

- 임계값을 바꾸면 **로봇과 콘솔 양쪽**에서 같은 값이 되게 합니다(콘솔은 `robot/config.py` 상수를 읽음).

## 6. PC 콘솔 실행 · 화면 확인

노트북을 핫스팟 네트워크에 둔 상태에서, 담당 로봇 IP·카메라 URL 로 콘솔을 엽니다([robot_console](../test_PC/robot_console/README.md)).

```powershell
python -m test_PC.robot_console.server --robot A --robot-ip 192.168.137.x --allow-real ^
  --cam http://mechdog-a-cam.local:81/stream --relay-lidar
```

- `--robot-ip` 는 3.6 의 시리얼 IP. 자동 탐색은 `--robot-ip auto`(핫스팟에 HELLO 방송).
- 브라우저에서 `http://127.0.0.1:8090` 을 엽니다. 카메라 영상, 로봇 ID·상태, LiDAR 점을 확인합니다.

## 7. 점검 순서 (받침대에서)

1. **잠긴 상태 확인:** 상태가 `stopped / boot` 로 보이고 영상·LiDAR 가 나오는지.
2. **잠금 해제:** 대시보드의 해제 버튼. 상태가 `idle` 로 바뀌는지(배터리·Wi-Fi 가 정상이어야 해제됨).
3. **정지·비상 정지 먼저:** 비상 정지를 눌러 `stopped / estop` 이 되는지. 해제 후 진행.
4. **이동:** 누르고 있는 동안만 전진·후진·좌·우, 놓으면 정지하는지(받침대에서 다리 움직임으로 확인).
5. **통신 끊김 정지:** 노트북 Wi-Fi(핫스팟)를 잠깐 끊었을 때 로봇이 스스로 멈추고 `link_lost` 로 잠기는지.
6. **라이다:** `--relay-lidar` 로 LiDAR 점이 도는지. 라이다가 끊겨도 로봇은 멈추지 않습니다(규약 7절).
7. 바닥 주행은 위가 모두 정상일 때, 사용자 확인 범위에서만.

## 8. 문제 해결

- **로봇이 Wi-Fi 에 안 붙음:** 핫스팟이 2.4GHz 인지, `secrets.h` SSID/비밀번호가 정확한지. 시리얼에 `WiFi OK` 가 안 뜨면 재시도 중입니다.
- **해제가 안 됨(`reset_denied`):** 배터리가 낮거나(≥6800mV 필요) Wi-Fi 가 불안정하거나 동작 그룹 중입니다. 충전 후 재시도.
- **상태가 안 보임:** 콘솔 `--robot-ip` 가 맞는지, 방화벽에서 개인 네트워크를 허용했는지.
- **`imu_unknown`:** 기본값(안전)입니다. IMU 축·초기화를 실물에서 확인한 뒤 `motion_mechdog.cpp` 의 `MECH_ENABLE_IMU` 로 켭니다.
- **동작 그룹이 비상 정지로 바로 안 멈춤:** 벤더 라이브러리에 중단 API 가 없어 그룹이 끝난 뒤 멈춥니다(규약 3.3절). 현장 기능엔 동작 그룹을 쓰지 않습니다.
- **카메라 영상 없음:** `/status` 의 로봇 ID·`camera.ok` 확인. 영상 없음은 "사람 없음"이 아니라 `unknown` 입니다.

## 9. 안전 · 실물 미검증

- 이 Arduino 펌웨어의 **코어 안전 로직**(명령·감시·래치·저전압·텔레메트리)은 `robot/` 과 같은 시나리오 35개로 검증했고,
  비벤더 코드는 arduino-cli 로 컴파일됩니다. 그러나 **벤더 동작 백엔드와 실제 로봇 동작은 아직 미검증**입니다.
- **배터리 단위(mV 가정)·라이다 UART 방향·IMU 축**은 실물에서 확인해 `mech_config.h`·문서를 고칩니다.
- 실제 로봇을 움직이거나 펌웨어를 굽는 일은 **사용자 확인 범위**에서만 합니다.
