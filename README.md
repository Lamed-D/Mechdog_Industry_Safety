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
3. **잠금 해제** 후 W/A/S/D로 움직입니다. Space = 정지, Esc = 비상 정지.

## 펌웨어 올리기

올리기 전에 항상 기존 펌웨어를 백업합니다.

- **로봇 본체 — 사람이 직접.** AI가 업로드 파일을 만들고 순서를 채팅으로 안내합니다. 가이드: [ai/firmware.md](ai/firmware.md) 2.2절(MicroPython), 4.2절(Arduino)
- **카메라(비전 모듈) — AI 에이전트가 올리고 확인.** 사람은 본체 전원 끄기·케이블 연결만 합니다. 끝나면 AI가 설정 내용을 채팅으로 알려 줍니다(점검용 AP 기본 비밀번호 `password`).
- 실물 점검 순서 → [ai/robot-tests.md](ai/robot-tests.md)

### 로봇 A/B 구분

로봇마다 다른 값은 **로봇 ID(A 또는 B)** 하나뿐입니다. 직접 하거나 AI에게 "로봇 A용으로 만들어 줘"처럼 ID를 말해 맡기면 됩니다.

| 대상 | ID 정하는 법 | 결과 |
| --- | --- | --- |
| 본체 MicroPython | 저장소 폴더에서 `python -m ai.tools.make_robot_files A` (B면 `B`, 생략하면 B) | `build/robot_files_A/` 에 올릴 파일이 생김. 이 폴더 파일을 가이드 순서대로 올림 |
| 본체 Arduino | `firmware/robot/arduino/secrets.example.h` 를 `secrets.h` 로 복사해 `MECH_ROBOT_ID 'A'` 와 Wi-Fi 값을 적고 빌드 | 로봇마다 `secrets.h` 값을 바꿔 다시 빌드 (`secrets.h` 는 커밋되지 않음) |
| 카메라 | 빌드는 A/B 공통 하나. 굽고 나서 시리얼로 `set robot A` | 주소가 `mechdog-a-cam.local` / `mechdog-b-cam.local` 로 나뉨 |

- 카메라 ID는 **그 카메라가 달린 로봇의 ID**와 같게 합니다. 두 로봇이 같은 ID를 쓰면 대시보드가 섞입니다.
- 대시보드도 같은 ID로 실행합니다: `python -m dashboard.server --robot A ...`
