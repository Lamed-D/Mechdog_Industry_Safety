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
