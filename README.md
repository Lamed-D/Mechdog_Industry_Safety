# Mechdog Industry Safety

Hiwonder MechDog 사족보행 로봇으로 산업 현장 안전을 돕는 프로젝트입니다.
개발은 AI가 하고, 사람은 이 문서만 보면 됩니다. 자세한 내용은 `docs/ai/` 링크에 있습니다.

## 장비

| 장비 | 수량 | 용도 |
| --- | --- | --- |
| MechDog (다리 4개, ESP32 메인 보드) | 1 | 로봇 본체 |
| ESP32-S3 비전 모듈 (로봇 앞쪽) | 1 | 카메라 영상 → 노트북 |
| RPLIDAR A1M8 (로봇 등 위) | 1 | 대시보드에 표시만 |
| Windows 노트북 | 1 | 대시보드·판단 |

나중에 같은 세트를 하나 더 두고(A/B) 두 대가 협업하도록 넓힐 예정입니다. → [장비 상세](docs/ai/hardware.md)

## 노트북 준비

저장소 맨 위 폴더에서 CMD로 코드 검사를 한 번 돌립니다(장비에 접속하지 않음).

```cmd
test_PC
un.cmd all
```

## 실제 로봇과 연결

1. 노트북을 비전 모듈 Wi-Fi(`HW_ESP32S3CAM`)에 연결합니다.
2. 로봇 전원을 켜고 아래를 실행한 뒤 `http://127.0.0.1:8090` 을 엽니다.

   ```cmd
   python -m dashboard.server --robot-ip auto --allow-real --cam http://192.168.5.1:81/stream
   ```

   로봇에 올린 ID가 B면 `--robot B` 를 붙입니다(기본 A).
   노트북 핫스팟(맞춤 카메라 펌웨어)으로 연결할 때는 주소가 달라집니다 → [대시보드 상세](docs/ai/dashboard.md).
3. 화면에서 **잠금 해제** 후 W/A/S/D로 움직입니다. Space = 정지, Esc = 비상 정지.

→ [대시보드 상세·라이다 연결](docs/ai/dashboard.md)

## 펌웨어 올리기 (사람이 직접)

- **올리기 전에 항상 기존 펌웨어를 백업합니다.** 원래 장치 파일은 `backups/device-original/` 에 있습니다.
- 로봇 본체: Hiwonder Python Editor로 파일을 올립니다. → [본체 올리기](docs/ai/firmware.md)
- 비전 모듈: Arduino IDE로 `firmware/vision_cam/` 을 올립니다. → [카메라 올리기](docs/ai/firmware.md)
- 실물 점검 순서와 결과 양식 → [실물 확인](docs/ai/robot-tests.md)

## 폴더

| 폴더 | 내용 |
| --- | --- |
| `dashboard/` | 노트북 대시보드(영상·조작·라이다) |
| `robot/`, `custom_sensors/` | 로봇 본체 MicroPython 코드 |
| `firmware/` | 본체 Arduino 판, 비전 모듈 펌웨어 |
| `host/`, `ros2/` | 노트북 쪽 통신·카메라·라이다 처리 |
| `test_PC/`, `tests/`, `tools/` | 시험·빌드 도구 |
| `docs/ai/` | AI용 규칙·설계 문서 |
