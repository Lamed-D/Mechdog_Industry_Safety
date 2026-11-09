# 비전 모듈(ESP32-S3 카메라) 맞춤 펌웨어

로봇 A·B 앞쪽 비전 모듈에 올리는 우리 펌웨어(`firmware/vision_cam`, v0.1.0)의 설치·설정·확인·복구·빌드 안내입니다.
**목표는 카메라 영상을 Wi-Fi로 Pi 5에 보내는 것**입니다. 쓰러진 사람 인식은 Pi 5가 영상으로 합니다.

> **이 문서의 굽기·백업 명령은 사용자가 직접 실행합니다.** 에이전트는 카메라·로봇에 펌웨어를 올리지 않습니다.
> 이 펌웨어는 PC에서 컴파일만 확인했고 **실물에서 아직 돌려 보지 않았습니다**(10절).

## 1. 무엇이 달라지나

| 항목 | 제조사 기본 영상 펌웨어(구입 당시) | 맞춤 펌웨어 |
| --- | --- | --- |
| Wi-Fi | 카메라가 AP `HW_ESP32S3CAM`을 열고 휴대폰이 붙음(`192.168.5.1`) | **전용 공유기에 STA로 접속.** Pi 5가 로봇 A·B 카메라를 동시에 받음 |
| 영상 | 웹 화면의 Image 보기 | `:81/stream`(MJPEG, **최신 프레임만**), `/capture`(JPEG 한 장), `/status`(JSON) |
| 이름 | 고정 IP 하나 | mDNS `mechdog-a-cam.local` / `mechdog-b-cam.local` + 로봇 ID 확인 |
| Wi-Fi 절전 | 미확인 | **끔**(지연·끊김 방지) |
| 접속 실패 시 | — | 30초 뒤 점검용 AP `MECHDOG-A-CAM`(비밀번호 설정한 경우만), STA 재시도 계속 |
| 메인 보드 I2C | 응답 없음(오류 19로 보임) | 공식 `ESP32S3Cam` 읽기에 규격대로 **"결과 없음"** 응답 + 상태 레지스터 `0xE0` |
| 카메라 안 인식(얼굴·색·라인) | 기능별 별도 펌웨어 | **넣지 않음**(9절) |
| 감시 | 미확인 | 작업 워치독 10초, 카메라 재초기화, Wi-Fi 재접속, 10분 고립 시 재부팅 |
| 설정 저장 | — | USB 시리얼 명령으로 카메라 안(NVS)에 저장. **저장소에는 비밀번호 없음** |

통신 형식(HTTP 머리글, I2C 명령표)은 [통신 규약 11절](protocol.md#11-비전-모듈-맞춤-펌웨어-영상i2c)에 있습니다.

## 2. 파일

| 경로 | 내용 |
| --- | --- |
| `firmware/vision_cam/release/mechdog_vision_cam_v0.1.0_0x0.bin` | **바로 굽는 합본 이미지**(주소 `0x0`). 부트로더·파티션 표·앱 포함, 약 1.06 MB |
| `firmware/vision_cam/release/*.sha256` | 위 파일의 SHA-256 |
| `firmware/vision_cam/*.ino, *.cpp, *.h` | 소스(한국어 주석) |
| `firmware/vision_cam/config.h` | 기본값(해상도·품질·포트·I2C 주소·시간) |
| `firmware/vision_cam/secrets.example.h` | 빌드 때 설정을 넣고 싶을 때의 예시. 실제 `secrets.h`는 커밋 금지(.gitignore) |
| `tools/build_vision_cam.py` | 컴파일·합본 이미지 생성 |
| `host/vision/camera_client.py` | Pi 5 수신(상태·캡처·스트림 최신 프레임) |
| `tools/mock/mock_camera.py` | PC 시험용 가짜 카메라 서버(합성 바이트만) |

## 3. 하드웨어 근거

| 항목 | 값 | 근거 |
| --- | --- | --- |
| 칩 | ESP32-S3 | 제조사 비전 모듈 안내·플래시 안내(ChipType ESP32-S3) |
| 플래시 | 4 MB 설정, DIO, 80 MHz, 합본을 `0x0000`에 씀 | 제조사 기본 영상 펌웨어 이미지 머리글(4MB·DIO·80m)과 제조사 플래시 안내 |
| PSRAM | **옥탈(OPI)** | 제조사 기본·인식 펌웨어 모두 옥탈 PSRAM 지원으로 빌드됨(이미지 안 문자열) |
| 카메라 핀 | ESP32-S3-EYE 배치(XCLK 15, SIOD 4, SIOC 5, D0~D7 = 11·9·8·10·12·18·17·16, VSYNC 6, HREF 7, PCLK 13, PWDN·RESET 없음) | 제조사 비전 예제 전부가 이 보드 정의를 고름. 기본 영상 펌웨어에도 같은 카메라 모듈 이름이 들어 있음 |
| 카메라 센서 | 2백만 화소. 드라이버가 자동 인식(OV2640 등) | 제조사 안내 그림 "2-Megapixel camera". `/status`의 `camera.sensor`로 실물 확인 |
| 카메라 XCLK | 15 MHz | 제조사 예제와 같은 값 |
| I2C(메인 보드 쪽) | SDA IO47, SCL IO48, 100 kHz, 슬레이브 | 제조사 카메라 예제 전부 같은 핀·속도 |
| I2C 주소 | 메인 보드 공식 라이브러리 레지스터형 `0x53`, 제조사 기능별 카메라 펌웨어 `0x52` | 제조사 메인 보드 Arduino 라이브러리와 카메라 예제(7절) |
| USB | CH340 USB-시리얼(내장 USB CDC 아님) | 제조사 플래시 안내의 장치 관리자 그림 |
| 전원 | 5V 2A 이상 | 제조사 안내(부족하면 영상 깨짐) |

핀 배치가 실물과 다르면 카메라 초기화가 실패합니다. 그때 시리얼에 `camera FAILED`가 나오고 `/status`의 `camera.ok`가 `false`입니다.
이 경우 다른 보드 정의로 추측해 바꾸지 말고 결과를 이슈로 남깁니다(제조사 예제의 보드 정의가 하나뿐이라 후보가 없음).

## 4. 설치 (미리 빌드한 bin, 사용자)

로봇 한 대씩 합니다. 아래는 로봇 A 기준이며 B도 같고 `set robot B`만 다릅니다.

### 4.1 준비

- [ ] 본체 전원을 끄고, 비전 모듈 IIC 케이블을 빼서 **카메라만 PC에 연결**합니다.
      **이 항목은 공식 문서에 있는 절차가 아니라 우리 안전 권고입니다.** 제조사 플래시 안내는 "ESP32-S3가 잡은 COM 포트를 고르라"고만 합니다.
      USB 전원과 본체 전원(IIC 케이블)이 동시에 들어갈 때 역급전 여부를 확인하지 못했으므로 겹치지 않게 하자는 것입니다(실물 미확인).
- [ ] Type-C **데이터** 케이블. 충전 전용 케이블은 안 됩니다.
- [ ] 카메라를 꽂았다 뺐다 하며 생기는 COM 포트(장치 관리자 → 포트, `USB-SERIAL CH340`)를 확인합니다. 메인 보드 포트(COM6 등)와 혼동하지 않습니다.
- [ ] 카메라 포트를 쓰는 프로그램(에디터, 시리얼 모니터)을 모두 닫습니다.
- [ ] esptool 준비. Arduino IDE ESP32 패키지에 들어 있습니다:
      `%LOCALAPPDATA%\Arduino15\packages\esp32\tools\esptool_py\<버전>\esptool.exe`
      (또는 `pip install esptool` 뒤 `python -m esptool`). 아래 예시는 `esptool`로 줄여 씁니다.
- [ ] 이미지 확인(PowerShell): `Get-FileHash firmware\vision_cam\release\mechdog_vision_cam_v0.1.0_0x0.bin -Algorithm SHA256`
      값이 같은 폴더 `.sha256` 파일과 같아야 합니다.

### 4.2 (1) 현재 플래시 전체 백업 — 반드시 먼저

```powershell
esptool --chip esp32s3 --port COM10 flash-id
esptool --chip esp32s3 --port COM10 --baud 460800 read-flash 0 ALL C:\camera-backup\robotA_cam_full.bin
```

- `COM10`은 4.1에서 찾은 카메라 포트로 바꿉니다. `flash-id`의 `Detected flash size`를 기록합니다.
- 백업 파일은 **저장소 밖**에 둡니다(장치 고유 정보 포함 가능). 크기가 플래시 크기(예: 4 MB = 4,194,304바이트)와 같은지 봅니다.
- esptool 4.x는 `read_flash`·`flash_id`처럼 밑줄 명령을 씁니다.
- 연결이 안 되면 포트 점유·케이블을 먼저 봅니다. 버튼 조합은 보드 표시를 확인하기 전에는 추측하지 않습니다.

### 4.3 (2) 맞춤 펌웨어 굽기

```powershell
esptool --chip esp32s3 --port COM10 --baud 460800 write-flash 0x0 firmware\vision_cam\release\mechdog_vision_cam_v0.1.0_0x0.bin
```

제조사 플래시 다운로드 도구를 쓸 때도 제조사 안내와 같은 설정입니다: ChipType **ESP32-S3**, 파일 하나 체크, 주소 **0x0000**,
SPI SPEED **80MHz**, SPI MODE **DIO**, BAUD **460800**, 나머지 기본값, `START`. **ERASE는 누르지 않습니다**(백업이 있어도 불필요).

- 쓰는 중에 케이블을 빼거나 전원을 끄지 않습니다.
- 완료 뒤 카메라가 다시 시작합니다(esptool 기본 동작: 하드 리셋).

### 4.4 (3) Wi-Fi·로봇 ID 설정 (USB 시리얼)

1. 시리얼 터미널을 카메라 포트, **115200 bps**, 줄 끝 **Newline(또는 CR+LF)** 으로 엽니다.
   - Arduino IDE: 도구 → 포트 선택 → 시리얼 모니터, 오른쪽 아래 `115200 baud`, `Newline`.
   - 또는 `python -m serial.tools.miniterm COM10 115200` (pyserial 필요).
2. 카메라를 다시 꽂거나 리셋하면 다음과 비슷한 줄이 나옵니다:

   ```text
   [cfg] 설정 명령은 help
     robot    A
     ssid     (비어 있음)
     ...
   [cam] camera ok, psram yes
   [cam] i2c slave 0x53 ok
   ```

3. 다음을 한 줄씩 입력합니다(값은 예시입니다. 실제 비밀번호를 이슈·문서·채팅에 붙이지 않습니다).

   ```text
   set robot A
   set ssid <시연 전용 공유기 SSID>
   set pass <공유기 비밀번호>
   set ap_pass <점검용 AP 비밀번호, 8자 이상>      (선택)
   set key <접근 키>                                (선택, 4.6 참고)
   show
   reboot
   ```

   - `show`는 비밀번호·키를 가리고 "설정됨"만 표시합니다.
   - 설정은 카메라 안(NVS)에만 저장되고 **다시 구워도 지워지지 않을 수 있습니다.** 지우려면 `clear pass` 처럼 씁니다.
   - 공백이 있는 SSID도 그대로 쓰면 됩니다(`set ssid My Router`).
4. 재시작 뒤 10초마다 상태 줄이 나옵니다. `sta 192.168.x.y rssi -55 | cam 1 fps 0.0 clients 0` 처럼 **`sta`와 IP**가 보이면 접속 성공입니다.
   (받는 사람이 없으면 촬영을 쉬므로 fps 0.0이 정상입니다.)
5. 30초 넘게 접속이 안 되고 `ap_pass`를 넣었으면 AP `MECHDOG-A-CAM`이 켜집니다. 그 AP에 노트북을 붙여
   `http://192.168.4.1/status`로 상태를 볼 수 있습니다. 공유기 SSID·비밀번호를 다시 확인합니다.

공유기에서 두 카메라에 **DHCP 예약(고정 IP)** 을 해 두기를 권장합니다. mDNS가 안 되는 네트워크에서도 주소가 바뀌지 않습니다.
빌드 때 넣고 싶으면 `secrets.example.h`를 `secrets.h`로 복사해 같은 값을 넣고 직접 빌드합니다(6절). 시리얼로 저장한 값이 우선합니다.

### 4.5 (4) 동작 확인

같은 공유기에 붙은 PC에서(키를 설정했으면 주소 끝에 `?key=<키>`):

| 확인 | 주소 | 기대 결과 |
| --- | --- | --- |
| 상태 | `http://mechdog-a-cam.local/status` | JSON에 `"robot":"A"`, `"camera":{"ok":true,...}`, `"wifi":{"mode":"sta",...}` |
| 한 장 | `http://mechdog-a-cam.local/capture` | 사진 한 장 |
| 영상 | `http://mechdog-a-cam.local:81/stream` | 브라우저에 실시간 영상 |
| 수신 지연 | 영상 보면서 `/status` 새로 고침 | `camera.fps`, `frame_age_ms`(작을수록 좋음) |

- `.local` 이름이 안 열리면 시리얼 로그의 IP로 엽니다(Windows는 mDNS가 안 될 수 있음).
- Pi 5(또는 PC)에서 파이썬으로:

  ```python
  from host.vision.camera_client import CameraClient, CameraEndpoint, LatestFrameReceiver
  cam = CameraEndpoint("A", "mechdog-a-cam.local", key=None)   # 키를 썼으면 key="..."
  print(CameraClient(cam).status())
  rx = LatestFrameReceiver(cam).start()
  # 잠시 뒤
  print(rx.state())   # {'status': 'streaming', ...}
  ```

- 확인 뒤 **영상·사진 파일을 저장하거나 이슈에 붙이지 않습니다**(사람이 찍힐 수 있음). 결과는 숫자(fps, frame_age_ms, rssi)만 남깁니다.

### 4.6 접근 키

`set key`를 쓰면 키 없는 요청은 `401`입니다. 시연 전용 공유기에 다른 사람이 붙을 수 있으면 켜 두기를 권장합니다.
HTTPS가 아니므로 공유기 안에서 엿볼 수 있는 사람에게는 보호가 되지 않습니다. 공유기 자체를 WPA2 이상, 외부와 분리해 씁니다.

### 4.7 본체 연결 후 메인 보드 확인

1. 카메라 USB를 빼고, 본체 전원이 꺼진 상태에서 IIC 케이블을 원래대로(본체 물리 IIC 포트 1) 연결합니다.
2. 본체를 켜면 카메라도 본체 전원으로 켜지고 같은 Wi-Fi 설정으로 접속합니다. 4.5를 다시 확인합니다(전원 부족이면 영상이 깨짐).
3. 메인 보드 REPL에서 기존 [vision_probe](../tools/bringup/vision_probe.py)를 [사용자용 비전 가이드](vision-firmware.md) 5절대로 실행합니다(모션 없음).
   기대: `status: observed`, `has_result: False`. **오류 19가 계속되면 7절(주소 바꾸기)** 을 봅니다.

## 5. 복구

문제가 있으면 둘 중 하나로 되돌립니다(사용자).

- **백업으로 되돌리기(가장 확실):**

  ```powershell
  esptool --chip esp32s3 --port COM10 --baud 460800 write-flash 0x0 C:\camera-backup\robotA_cam_full.bin
  ```

- **제조사 기본 영상 전송 펌웨어로:** 제조사 플래시 다운로드 도구로 제조사가 제공한 비전 모듈 기본 영상 전송 바이너리를
  4.3과 같은 설정(ESP32-S3, 0x0000, 80MHz, DIO, 460800)으로 굽습니다. 그러면 휴대폰 AP 방식(`HW_ESP32S3CAM`)으로 돌아갑니다.

맞춤 펌웨어가 시리얼에 아무것도 출력하지 않거나 계속 재시작하면, 로그 몇 줄(비밀번호 제외)을 이슈 #29에 남기고 복구합니다.

## 6. 직접 빌드 (개발자)

```powershell
python tools/build_vision_cam.py            # 컴파일만 → build/vision_cam (커밋 안 됨)
python tools/build_vision_cam.py --release  # + firmware/vision_cam/release/ 합본 bin·sha256
```

- 도구: Arduino IDE에 들어 있는 `arduino-cli`, ESP32 Arduino 코어 **3.3.12**(ESP-IDF 5.5.5), 같은 패키지의 esptool.
  다른 위치면 환경 변수 `ARDUINO_CLI`, `ESPTOOL_PATH`로 지정합니다.
- 보드 설정(FQBN): `esp32:esp32:esp32s3:PSRAM=opi,FlashMode=dio,FlashSize=4M,PartitionScheme=huge_app,CDCOnBoot=default,CPUFreq=240`
  - `PSRAM=opi`, `FlashMode=dio`, `FlashSize=4M`: 3절 근거. 실제 플래시가 더 커도 4MB 설정은 그대로 동작합니다.
  - `huge_app`: 앱 3 MB(OTA 없음). 현재 앱 약 1.0 MB.
  - `CDCOnBoot=default`(꺼짐): USB가 CH340 시리얼이므로 내장 USB CDC를 쓰지 않습니다.
- `--release`는 `secrets.h`가 있으면 멈춥니다(배포 이미지에 비밀번호가 들어가지 않게). 또 이미지 안 소스 경로에서 이 PC의 사용자 폴더를 지웁니다.
- 같은 소스·같은 코어면 같은 SHA-256이 나옵니다(두 번 빌드해 확인).
- 공개 라이브러리: Arduino-ESP32 코어(LGPL-2.1)와 그 안의 ESP-IDF·esp32-camera(Apache-2.0)만 씁니다. 추가 라이브러리 없음.

**제조사 개발 환경과의 차이:** 제조사 안내는 ESP32 Arduino 패키지 2.0.x(2.0.4·2.0.12)를 쓰고, 제조사 기본 펌웨어는 ESP-IDF 5.0 계열로 빌드됐습니다.
우리는 코어 3.3.12로 빌드합니다. 차이: 카메라 드라이버가 더 새 버전이고(SCCB가 새 I2C 드라이버, 포트 1), Wire 슬레이브 API는
이름이 같으며, 작업 워치독 설정 방식이 바뀌었습니다(`esp_task_wdt_reconfigure`). 제조사 인식 라이브러리(ESP-WHO)는 쓰지 않습니다.
2.0.x 코어로는 빌드를 확인하지 않았습니다.

## 7. I2C 주소 고르기

메인 보드 공식 라이브러리는 세대에 따라 두 형식을 씁니다. 펌웨어는 두 형식의 명령에 모두 답하지만 **주소는 하나만** 가질 수 있습니다.

| 메인 보드 라이브러리 | 증상 | 주소 |
| --- | --- | --- |
| 이전 세대(`face_recognition`, `color_recognition`만 있음 — 현재 사용자 장치) | 레지스터형(`0xB0` 등) | **`0x53`(기본)** |
| 최신 세대(`read_face`, `read_color` 있음) | 명령형(`0x01` 등) | `0x52` |

현재 장치(진단 결과 `read_face` 없음)는 이전 세대이므로 기본 `0x53`으로 빌드했습니다. 다만 이전 세대 Python 라이브러리의 실제 주소는
소스가 없어 확인하지 못했습니다(Arduino 라이브러리 기준 추정). 굽고 나서 4.7에서 오류 19가 계속되면 `config.h`의
`CAM_I2C_ADDR`를 `0x52`로 바꿔 직접 빌드(6절)한 뒤 다시 확인합니다. 결과는 이 표에 기록합니다.

## 8. 기본값과 근거

| 값 | 기본 | 근거 / 바꾸는 곳 |
| --- | --- | --- |
| 해상도 | VGA 640×480 | 사람 자세 판단 입력으로 충분, 두 대 동시 전송 대역 여유. `CAM_FRAME_SIZE` |
| JPEG 품질 | 12 | 한 장 약 20~40 KB 예상 **[가정]**. `CAM_JPEG_QUALITY` |
| 프레임 버퍼 | PSRAM 2개, 최신 프레임 모드 | 지연 최소화. PSRAM 없으면 QVGA·1개로 자동 낮춤 |
| 동시 스트림 | 2 | Pi 5 + 점검용 브라우저. `CAM_MAX_STREAM_CLIENTS` |
| 촬영 쉬기 | 10초 무요청 | 발열 감소. `CAM_IDLE_MS` |
| 새 프레임 대기 | 3초 | 넘으면 스트림 종료·캡처 503. `CAM_FRAME_WAIT_MS` |
| 재초기화 | 연속 실패 10회 | `CAM_FAILS_BEFORE_REINIT`. 재초기화 3회 실패 시 재부팅(전원 켠 뒤 최대 3번, 그 뒤 30초마다 재시도) |
| 워치독 | 10초 | `CAM_WDT_TIMEOUT_MS` |
| STA 재시도 / AP 전환 | 10초 / 30초 | `CAM_STA_RETRY_MS`, `CAM_STA_FALLBACK_MS` |
| 고립 재부팅 | 10분 | `CAM_NET_RESTART_MS`(SSID를 설정한 경우만) |
| 영상 방향 | 센서별 기본(OV2640 등 상하 반전) | 실물이 거꾸로면 `CAM_VFLIP`/`CAM_HMIRROR` |

## 9. 카메라 안 인식을 넣지 않은 이유

- 목표 기능(쓰러진 사람)은 카메라 안의 얼굴·색·라인 인식으로 할 수 없습니다. 얼굴 검출은 자세 정보가 아닙니다.
- 인식을 같이 돌리면 같은 칩에서 영상 압축·전송 속도가 떨어지고 메모리를 나눠 씁니다. 영상 전송이 우선입니다.
- `robot/vision.py`는 카메라 인식 결과로 로봇을 움직이지 않고 상태만 기록합니다(`fallen_person: unknown`).
- 그래서 I2C는 규격대로 "결과 없음"만 돌려줍니다. 메인 보드의 공식 읽기가 성공하는지는 **카메라 연결 확인** 용도로 씁니다.

## 10. 확인하지 못한 것

- 실물 동작 전부: 카메라 초기화(핀·센서), 옥탈 PSRAM 인식, STA 접속, mDNS, 실제 fps·지연·한 장 크기·발열, 두 대 동시 전송.
- 메인 보드 공식 라이브러리와의 I2C 응답(주소 0x53/0x52, 7절), Arduino 3.3.12 Wire 슬레이브의 실제 타이밍.
- 시리얼 설정 명령의 실제 입력(줄 끝 문자, 한글 출력 표시).
- 본체 전원으로 카메라와 Wi-Fi를 같이 켤 때의 전원 여유.
- 코어 2.0.x로의 빌드, 다른 카메라 보드 정의.

실물 확인 결과는 이슈 #29에 숫자 위주로 남기고, 확인되면 이 절과 [통신 규약 11절](protocol.md#11-비전-모듈-맞춤-펌웨어-영상i2c)을 고칩니다.
