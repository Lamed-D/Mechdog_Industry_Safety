# Mechdog Industry Safety

Hiwonder MechDog 사족보행 로봇으로 산업 현장 안전을 돕는 프로젝트입니다.

## 구성

| 폴더 | 무엇 |
| --- | --- |
| `firmware/robot/python/` | 로봇 본체 펌웨어 (MicroPython, 주) |
| `firmware/robot/arduino/` | 로봇 본체 펌웨어 (Arduino 판) |
| `firmware/vision/` | 앞쪽 카메라(비전 모듈) 펌웨어 (Arduino) |
| `dashboard/` | 노트북 대시보드 — 카메라 영상, 로봇 조종, 라이다 표시 |
| `ai/` | AI가 쓰는 규칙·설계 문서와 도구 (사람은 안 봐도 됨) |

장비: MechDog 1대 + 비전 모듈 + RPLIDAR A1M8(USB, 표시용) + Windows 노트북. 나중에 같은 세트 A/B 2대로 넓힙니다.

## Windows에서 처음 설치하기

두 대를 함께 사용할 때는 [두 로봇 협동 시나리오](#두-로봇-협동-시나리오)의 준비·실행 순서를 따릅니다.

1. Python 3.11 이상을 설치하고 설치 옵션에서 PATH 추가를 선택합니다. 새 PowerShell에서 `python --version`을 확인합니다. 로봇 본체에 파일을 올리려면 제조사의 **Hiwonder Python Editor**도 준비합니다. [Python 다운로드](https://www.python.org/downloads/windows/)
2. Vision을 빌드하려면 **Arduino IDE 2**를 설치합니다. IDE의 **File → Preferences → Additional boards manager URLs**에 `https://espressif.github.io/arduino-esp32/package_esp32_index.json`을 추가합니다. **Boards Manager**에서 **esp32 by Espressif Systems 3.3.12**를 선택해 설치합니다. [Arduino IDE 설치](https://support.arduino.cc/hc/en-us/articles/360019833020-Download-and-install-Arduino-IDE) · [Espressif 보드 패키지 설치](https://docs.espressif.com/projects/arduino-esp32/en/latest/installing.html)
3. 카메라를 USB로 설정하거나 USB LiDAR를 쓸 경우 `python -m pip install pyserial`을 실행합니다. 카메라를 데이터용 USB 케이블로 연결했는데 장치 관리자에 **USB-SERIAL CH340 (COM 번호)**가 없으면 케이블과 CH340 드라이버 설치 상태를 확인합니다.

### 자율주행 탭에서 순찰 실험하기

**먼저 [A4 인쇄용 태그 2장](ai/patrol-print/apriltag-stations-a4.pdf)을 다운로드하세요.** A4 세로·단면·실제 크기 100%로 출력합니다. A는 ID 0, B는 ID 1입니다. 개별 이미지도 받을 수 있습니다. [A PNG](ai/patrol-print/station-a-0.png) · [B PNG](ai/patrol-print/station-b-1.png)

선 기반 코스는 **밝은 무광 바닥 + 검은색 진행선 + 파란색 가로 정지 띠**로 만듭니다. 선 없는 코스는 태그만 배치합니다. 테이프 고르는 법부터 카메라 각도, 정지 위치 보정, 첫 완주 확인까지 순서대로 보려면 [현장 설치·첫 주행 안내](ai/patrol-setup.md)를 따르세요.

1. 노트북에 `python -m pip install "opencv-python-headless>=4.8"`을 설치합니다. 카메라만 연결한 상태에서는 `python -m dashboard.server --robot A --hotspot --sensors-only`로 시작합니다. 본체 주행 때는 `python -m dashboard.server --robot A --hotspot --allow-real`로 실행합니다. 대시보드 주소는 `http://127.0.0.1:8090`입니다.
2. **자율주행** 탭에서 방문 순서를 입력하고 각 **태그 인쇄** 링크를 열어 흰 여백까지 인쇄합니다. 기본 순서 `1,0`은 A(ID 0)에서 출발해 B(ID 1)에 들른 뒤 A에 돌아와 정지합니다. 코너에는 경유 태그를 추가할 수 있습니다.
3. **선 기반**은 밝은 바닥에 검은 선으로 폐곡선을 만들고 지점마다 파란 가로 띠를 붙입니다. 출발은 A의 띠를 막 지난 위치입니다. 영상 아래쪽에서 노란 점이 선을 따르는지, 띠에서 멈출 위치에 해당 태그 하나가 보이는지 확인합니다.
4. **선 없음**은 각 지점의 원하는 정지 위치에서 해당 태그 하나를 화면 중앙에 놓고 **도착 기준 저장**을 누릅니다. 기준은 노트북에 로봇 ID별로 저장됩니다. 인쇄 크기·렌즈 설정을 바꾸면 다시 저장합니다. 각 구간에서 다음 태그가 보이고 선택한 탐색 방향으로 다음 지점을 찾을 수 있도록 배치합니다.
5. 실물 주행은 연결 상태와 전방 초음파를 확인하고 **조종 → 잠금 해제 → 자율주행 → 한 바퀴 시작**을 누릅니다. 현재 목표와 방문 순서, 정지 사유가 탭에 표시됩니다. 운영자가 **정지** 또는 상단 **비상 정지(Esc)**로 개입할 수 있습니다. 중단 뒤 다시 시작하면 입력한 순서의 첫 지점부터 진행합니다.

첫 현장 확인에서는 두 모드의 완주 여부, 각 지점 정지 오차와 수동 개입 횟수를 기록합니다. 선·목표 가림, 전방 장애물, 카메라 단절, 탭 이탈에서 실제로 정지하는지도 확인합니다.

### 두 로봇 협동 시나리오

1. 본체 A와 B의 최신 **MicroPython** 업로드 파일을 각각 `python firmware/build.py A --only python`, `python firmware/build.py B --only python`으로 만듭니다. 사용자가 각 ID에 맞는 파일을 올리고 마지막에 `main.py`를 올립니다. 각 카메라도 대응하는 A/B ID로 연결합니다. [본체 업로드 순서](ai/firmware.md#22-업로드-순서-사용자-가이드)
2. 이 README의 쓰러짐 감지용 Python 환경과 사람·자세 모델 두 개를 준비합니다. 기존 단일 로봇 서버를 닫고, 아래 명령에서 두 IP를 실제 본체 주소로 바꿔 실행합니다. 카메라 자동 연결이 어려우면 끝에 `--team-cameras http://<A카메라IP>:81/stream http://<B카메라IP>:81/stream`을 붙입니다.

   ```powershell
   python -m dashboard.server --team <A본체IP> <B본체IP> --allow-real
   ```

3. **협동 시나리오** 탭에서 두 영상을 확인합니다. 예를 들어 순환 코스 `0,1,2`, 출발 A=`0`·B=`1`, 도움 요청 구역=`2`를 입력합니다. [태그 인쇄·코스 설치](ai/patrol-setup.md)를 따라 추가 지점도 준비하세요. 각 로봇을 진행 방향으로 놓고 각 화면에 자기 시작 태그 하나가 보이게 합니다. 선 없는 모드에서는 두 로봇 각각에 코스 전체 태그의 도착 기준을 저장합니다.
4. 앞이 비었는지 확인하고 두 카드에서 각각 **잠금 해제 → 공동 순찰 시작**을 누릅니다. 먼저 쓰러짐을 확인한 로봇은 그 자리에 멈춰 낮은 경보음을 반복합니다. 다른 로봇은 지정 구역에서 서 있는 사람을 확인하면 높은 호출음을 내고 5초 기다립니다. 사람이 길을 비우면 현장 로봇의 마지막 확인 태그까지 안내하고 도착음을 냅니다. 마지막 태그와 실제 쓰러짐 위치 사이의 구간은 현장 부저와 영상으로 확인합니다.
5. 운영 중에는 탭을 열어 둡니다. **전체 정지**는 이동과 추가 부저를 중단하고, **전체 비상 정지(Esc)**는 두 본체를 잠급니다. **사건 종료** 후 시작 태그에서 새 순찰을 시작할 수 있습니다. 실제로 사람이 뒤따르는지는 운영자가 확인합니다.

첫 실물 검증은 선 기반·선 없는 코스 각각에서 A 감지/B 안내와 B 감지/A 안내를 수행합니다. 현장 정지 유지, 호출 후 대기, 목적 태그, 장애물 앞 정지, 통신·영상 단절 시 양쪽 정지와 재출발 방지를 기록합니다.

### 인터넷을 유지하는 Wi-Fi 연결

1. 노트북을 인터넷 Wi-Fi 또는 이더넷에 연결합니다. Windows의 **설정 → 네트워크 및 인터넷 → 모바일 핫스팟**에서 해당 인터넷 연결을 공유 원본으로 선택하고, 공유 방식은 **Wi-Fi**, 대역은 **2.4 GHz**로 설정한 뒤 켭니다. [Windows 모바일 핫스팟 설정](https://support.microsoft.com/en-us/windows/experience/connectivity-networking/use-your-windows-device-as-a-mobile-hotspot)
2. 본체와 카메라에 **Windows 모바일 핫스팟의 이름과 비밀번호**를 설정합니다. 노트북은 기존 인터넷 연결을 계속 사용합니다. 본체, 카메라, 대시보드에 모두 같은 로봇 ID를 사용합니다.

### 펌웨어 빌드 및 Wi-Fi 파일 생성

저장소 폴더의 PowerShell에서 실행합니다. 예시는 로봇 **B**입니다. 로봇 A라면 명령과 경로의 ID를 A로 바꿉니다.

```powershell
python firmware/build.py B --wifi-setup
```

- 한 번 입력한 핫스팟 이름과 비밀번호는 `build/robot_B/wifi/secrets.py`에 저장됩니다. 비밀번호 입력은 화면에 표시되지 않습니다. 이 파일은 본체 업로드와 카메라 Wi-Fi 설정에 쓰이며 평문 값이 들어 있으므로 공유하지 마세요.
- 본체 파일은 `build/robot_B/python/`, 카메라 합본은 `build/robot_B/vision/latest/`에 생깁니다. 카메라만 다시 빌드하려면 `python firmware/build.py B --only vision`을 사용합니다. 본체만 준비하려면 `python firmware/build.py B --only python --wifi-setup`을 사용합니다.
- 예비 본체 Arduino 판은 `python firmware/build.py B --only arduino`로 빌드합니다. 제조사 라이브러리 설치와 `secrets.h` 설정은 별도입니다. [본체 Arduino 빌드 및 업로드](ai/firmware.md#4-메인-보드-arduino--예비유지)
- CLI를 찾지 못하면 `--arduino-cli "C:\Program Files\Arduino IDE\resources\app\lib\backend\resources\arduino-cli.exe"`를 빌드 명령에 추가하고 설치 위치에 맞게 바꿉니다. 여러 번 쓸 때는 Windows의 **계정의 환경 변수 편집**에서 사용자 `Path`에 실행 파일이 들어 있는 **폴더**를 추가하고, 새 PowerShell에서 `Get-Command arduino-cli`로 확인합니다. 사용자 환경 변수 `ARDUINO_CLI`에 실행 파일 전체 경로를 지정해도 됩니다. 탐색 순서는 명령줄, `ARDUINO_CLI`, `PATH`, IDE 설치 폴더입니다.

### 로봇 본체에 올리기

1. 로봇을 받침대에 올리고 다리 주변을 비웁니다. Hiwonder Python Editor로 **본체 COM 포트**에 연결하고 REPL에서 Ctrl+C로 자동 실행을 중단합니다.
2. 생성한 `build/robot_B/wifi/secrets.py`를 본체 최상위에 업로드합니다.
3. `build/robot_B/python/`에서 다음 파일을 순서대로 Download 합니다. `netutil.py` → `motion.py` → `roles.py` → `config.py` → `proto.py` → `vision.py` → `sonar.py` → `comm.py` → `lidar_bridge.py` → `core.py` → `app.py`.
4. REPL에서 `import app`이 성공하면 **마지막에 `main.py`**를 올립니다. 본체를 재부팅하고 오류 없이 핫스팟에 연결되는지 확인합니다. [본체 업로드 및 복구](ai/firmware.md#22-업로드-순서-사용자-가이드)

### Vision 모듈에 올리고 Wi-Fi 설정하기

1. **본체 전원을 끄고 카메라 IIC 케이블을 분리**합니다. 데이터용 USB로 카메라만 노트북에 연결합니다. 장치 관리자에서 CH340의 COM 번호를 확인하고 포트를 사용하는 시리얼 모니터를 닫습니다.
2. 처음 설치할 때는 아래처럼 해시를 확인하고 합본을 씁니다. `COM7`은 실제 카메라 포트로 바꿉니다. `flash-id`에서 **ESP32-S3**가 확인될 때만 쓰기 명령을 실행합니다.

   ```powershell
   python -m pip install "esptool>=5,<6"
   $image = 'build/robot_B/vision/latest/mechdog_vision_cam_0x0.bin'
   $expected = ((Get-Content ($image -replace '\.bin$', '.sha256')) -split '\s+')[0]
   if ((Get-FileHash $image -Algorithm SHA256).Hash -ne $expected) { throw 'Vision 합본 SHA256 불일치' }
   python -m esptool --chip esp32s3 --port COM7 flash-id
   ```

   ```powershell
   python -m esptool --chip esp32s3 --port COM7 --baud 460800 write-flash 0x0 $image
   ```

   기존 맞춤 펌웨어를 업데이트하면서 설정을 유지하려면 `0x10000 build/robot_B/vision/compile/vision.ino.bin`을 씁니다. 전체 지우기(ERASE)는 실행하지 마세요. 쓰는 동안 USB나 전원을 분리하지 마세요.

3. 같은 Wi-Fi 값을 카메라에 저장합니다. 이 명령은 본체용 `secrets.py`를 읽어 로봇 ID와 Wi-Fi를 카메라에 USB 시리얼로 저장하고 재부팅합니다.

   ```powershell
   python -m firmware.builder.configure_vision_wifi B --port COM7
   ```

   수동 설정은 Arduino IDE 시리얼 모니터에서 **115200, Newline**으로 열고 `set robot B`, `set ssid <핫스팟 이름>`, `set pass <핫스팟 비밀번호>`, `reboot`를 한 줄씩 전송합니다.
4. 시리얼 상태 줄에서 `sta`와 카메라 IP를 확인합니다. 브라우저에서 `http://<카메라 IP>/status`의 `robot`과 `camera.ok`를 확인하고, `http://<카메라 IP>:81/stream`을 열어 영상이 나오는지 봅니다. USB를 빼고 **본체 전원이 꺼진 상태에서** 카메라 IIC 케이블을 본체 물리 IIC 포트 1에 다시 연결합니다.

## 대시보드 실행

Windows 모바일 핫스팟을 켠 상태에서 로봇 전원을 켜고, 저장소 폴더에서 실행합니다. 브라우저로 `http://127.0.0.1:8090`을 엽니다.

```powershell
python -m dashboard.server --robot B --hotspot --allow-real
```

- 카메라 자동 탐색이 안 되면 `--cam http://<카메라 IP>:81/stream`을 붙입니다. USB LiDAR를 쓰면 `--lidar-usb COM3`을 추가하고 실제 포트 번호로 바꿉니다.
- 처음에는 화면에서 로봇 ID, 배터리, 잠금 상태와 영상을 확인합니다. 조종할 때 **잠금 해제** 후 W/A/S/D를 사용합니다. Space는 정지, Esc는 비상 정지입니다. [실물 점검 순서](ai/robot-tests.md)

### 쓰러짐 감지와 사진 검토

Windows 64비트 Python 3.13 환경에서 최초 한 번 실행합니다. 모델과 검토 기록은 노트북의 사용자 데이터 폴더에 보관합니다.

```powershell
python -m pip install "mediapipe==0.10.32" pillow
$data = Join-Path $env:LOCALAPPDATA MechDog
New-Item -ItemType Directory -Force $data | Out-Null
curl.exe --fail --location https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task --output "$data/pose_landmarker_lite.task"
curl.exe --fail --location https://storage.googleapis.com/mediapipe-models/object_detector/efficientdet_lite0/int8/1/efficientdet_lite0.tflite --output "$data/efficientdet_lite0.tflite"
```

카메라만 연결한 경우 아래처럼 실행합니다. A/B는 실제 카메라 ID를 사용합니다. 본체를 조종하는 경우 기존 대시보드 실행 명령에 `--fall-detection`을 추가합니다.

```powershell
python -m dashboard.server --robot A --hotspot --sensors-only --fall-detection
```

**쓰러짐 로그**에서 사건을 열면 박스가 표시된 첫 의심·감지 확인 사진을 비교하고 확대할 수 있습니다. **쓰러짐 확인**, **오탐**, **판단 보류**를 고른 뒤 메모와 함께 저장합니다. 같은 사람은 두 사진에서 자세가 확인돼야 기록되며 이후 30초간 중복을 억제합니다. 기록은 재시작 후에도 조회할 수 있습니다.

본체 연결 모드에서 실제 카메라로 쓰러짐을 확인하면 현재 이동을 취소하고 30초간 이동·일어서기·잠금 해제를 차단합니다. 이후 새로 조종해야 움직입니다. 센서 전용 모드는 카메라만 사용합니다.

**쓰러짐 로그 → 시연 사진**에서 두 장을 다시 분석하고 판정을 연습할 수 있습니다. 시연용 원본은 `%LOCALAPPDATA%\MechDog\samples\replay\first.jpg`와 같은 폴더의 `second.jpg`입니다. 같은 사람을 연이어 촬영한 사진을 사용합니다. 시연 결과는 전용 보관함에 저장하며 로봇에 명령을 보내지 않습니다.

저대역폭 카메라 이미지는 `python firmware/build.py A --only vision --profile fall`로 빌드한 뒤 위의 카메라 업데이트 절차로 적용합니다. 이 설정은 카메라 전송 해상도를 480×320으로 낮춥니다.
