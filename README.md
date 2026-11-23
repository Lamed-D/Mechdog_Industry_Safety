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

## 로봇 조종하기

1. 노트북을 비전 모듈 Wi-Fi(`HW_ESP32S3CAM`)에 연결하고 로봇 전원을 켭니다.
2. 저장소 폴더에서 실행한 뒤 브라우저로 `http://127.0.0.1:8090` 을 엽니다.

   ```cmd
   python -m dashboard.server --robot-ip auto --allow-real --cam http://192.168.5.1:81/stream
   ```

   로봇 ID가 B면 `--robot B`, 라이다를 USB로 꽂았으면 `--lidar-usb COM번호` 를 붙입니다(처음 한 번 `pip install pyserial`).

   로봇과 비전 모듈이 Windows 모바일 핫스팟에 연결된 구성에서는 아래 명령으로 둘 다 자동으로 찾습니다. USB 라이다가 있으면 예시의 포트 번호를 실제 COM 번호로 바꿉니다.

   ```cmd
   python -m dashboard.server --hotspot --allow-real --lidar-usb COM3
   ```

3. **잠금 해제** 후 W/A/S/D로 움직입니다. Space = 정지, Esc = 비상 정지.

## 펌웨어 올리기

- **로봇 본체 — 사람이 직접.** AI가 업로드 파일을 만들고 순서를 채팅으로 안내합니다. 가이드: [ai/firmware.md](ai/firmware.md) 2.2절(MicroPython), 4.2절(Arduino)
- **카메라(비전 모듈) — AI 에이전트가 올리고 확인.** 사람은 본체 전원 끄기·케이블 연결만 합니다. 끝나면 AI가 설정 내용을 채팅으로 알려 줍니다(점검용 AP 기본 비밀번호 `password`).
- 실물 점검 순서 → [ai/robot-tests.md](ai/robot-tests.md)

### 펌웨어 빌드 (로봇 A/B)

로봇마다 다른 값은 **로봇 ID(A 또는 B)** 하나뿐입니다. 저장소 폴더에서 명령 하나로 그 로봇용 파일이 `build/robot_<ID>/` 에 생깁니다.
직접 해도 되고, AI에게 "로봇 A용으로 빌드해 줘"라고 맡겨도 같은 명령을 씁니다.

```cmd
python firmware/build.py A              # 로봇 A: 본체 Python 파일 + 카메라 펌웨어
python firmware/build.py B --only python
```

| 생기는 폴더 | 내용 | 다음 |
| --- | --- | --- |
| `build/robot_A/python/` | 본체에 올릴 `.py` 12개 (ID A가 들어 있음) | **사람**이 Hiwonder Python Editor로 올림 → [가이드](ai/firmware.md) 2.2절 |
| `build/robot_A/vision/latest/` | 카메라 펌웨어 `mechdog_vision_cam_0x0.bin` (ID A가 기본값) | **AI**가 굽고 확인 |
| `build/robot_A/arduino/` | Arduino 판 (`--only arduino` 일 때만) | **사람**이 Arduino IDE로 올림. ID는 `secrets.h` 의 `MECH_ROBOT_ID` → 가이드 4.2절 |

- 처음 한 번 Arduino IDE와 ESP32 보드 패키지 3.3.12 가 있어야 카메라 빌드가 됩니다. 끝에 `[성공]/[실패]` 와 다음 할 일이 나옵니다.
- 로봇 B의 카메라 펌웨어만 다시 빌드하려면 `python firmware/build.py B --only vision`을 실행합니다. 설치 위치를 직접 지정하려면 아래 PowerShell 예시의 경로를 바꿔 실행하세요.

```powershell
python firmware/build.py B --only vision --arduino-cli "C:\Program Files\Arduino IDE\resources\app\lib\backend\resources\arduino-cli.exe"
```

- 계속 사용하려면 Windows의 **계정의 환경 변수 편집**에서 사용자 `Path`에 `arduino-cli.exe`가 들어 있는 **폴더**를 추가하세요. 새 PowerShell에서 `Get-Command arduino-cli`로 확인한 뒤 `--arduino-cli` 없이 빌드할 수 있습니다.
- 카메라 ID는 **그 카메라가 달린 로봇의 ID**와 같게 합니다. 두 로봇이 같은 ID를 쓰면 대시보드가 섞입니다.
- 대시보드도 같은 ID로 실행합니다: `python -m dashboard.server --robot A ...`
