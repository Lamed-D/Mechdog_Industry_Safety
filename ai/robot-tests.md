# 실물 확인 절차

사람이 실제 장비에서 따라 하는 확인 순서와 결과 양식입니다. 장비는 **MechDog 1대 + 앞쪽 ESP32-S3 비전 모듈 + 등 위 RPLIDAR A1M8 + Windows 노트북 1대**이며, 기록은 로봇 단위(ID A/B)로 합니다.
검증은 실물에서만 합니다. 컴파일 성공은 실물 합격이 아닙니다.

## 0. 공통 원칙

- **로봇 본체 업로드·전원·구동은 사람만** 합니다. 에이전트는 업로드 파일 생성·빌드·사용자 가이드까지 합니다.
- **카메라(비전 모듈) 백업·굽기·설정·확인은 에이전트가** 합니다. 케이블·전원 같은 물리 조작은 사람이 합니다([rules.md](rules.md) 4.1절).
- 승인에는 **대상 ID와 단계 범위**를 적습니다. 앞 단계 승인이 다음 단계(업로드·이동) 승인이 되지 않습니다.
- 메인 보드 COM과 카메라 COM(CH340)을 구분합니다. 번호는 재연결 때마다 다시 확인합니다.
- 첫 확인은 적재물 없이 **받침대 위**. 손으로 다리를 붙들지 않습니다. 바닥 주행은 빈 공간과 즉시 전원 차단 수단을 확보한 뒤.
- 발열·냄새·부팅 반복·예상치 못한 움직임·정지 실패면 **즉시 중단하고 전원 차단**, 다음 단계로 넘어가지 않습니다.
- 결과에는 실제로 본 값만 적고 `미실행`·`실패`·`측정 불가`를 **있는 그대로** 남깁니다. 얼굴·현장 영상, 비밀번호·키, 장치 일련번호, 개인정보는 남기지 않습니다(작업자는 별칭).
- 상세: 백업·업로드·복구 [firmware.md](firmware.md), 배선·전원 [hardware.md](hardware.md), 메시지 [protocol.md](protocol.md), 화면 [dashboard.md](dashboard.md).

## 1. 순서

한 단계가 정상일 때만 다음으로 갑니다.

| # | 단계 | 정상 결과 | 실패 시 |
| --- | --- | --- | --- |
| 1 | 외관·고정·배선·배터리, 라이다 고정·0° 방향 (전원 OFF) | 손상·느슨함 없음 | 고정 후 재확인 |
| 2 | **백업**: 메인 보드 `main.py`·설정, 카메라 플래시 전체(저장소 밖) | 대상별 백업 파일·해시 | 백업 없으면 중단 |
| 3 | 카메라 펌웨어 굽기·설정 — **에이전트** ([firmware.md](firmware.md) 6.5) | `/status`의 `robot` ID·`camera.ok=true`·`wifi.mode=sta`, `/capture`, `:81/stream`, 창을 닫고 다시 열어도 새 영상 | 백업으로 복구, 다음 단계 금지 |
| 4 | 로봇 Python 업로드 — **사용자**, 가이드 [firmware.md](firmware.md) 2.2: `python -m ai.tools.make_robot_files <ID>` → `secrets.py` → `netutil` → `motion` → `roles` → `config` → `proto` → `vision` → `comm` → `lidar_bridge` → `core` → `app`(`import app` 확인) → **마지막 `main.py`** | 예외·MemoryError 없음, Wi-Fi 연결, TEL에 ID·`boot` 래치·배터리 | 자동 실행 중단, 기존 `main.py` 복원 |
| 5 | 대시보드 연결·정지 (2절) | 잠금·해제·정지·ESTOP 모두 기대대로 | 원인 확인 전 재개 금지 |
| 6 | 통신 끊김 정지 (2절 6) | 로봇이 스스로 멈추고 `link_lost` 래치 유지 | 원인 확인 전 재개 금지 |
| 7 | LiDAR USB (3절) | 상태 Good, 화면에 점 | 케이블·전원·COM 포트 |

## 2. 대시보드 안전 확인 (받침대)

```cmd
python -m dashboard.server --robot <ID> --robot-ip <IP|auto> --allow-real --cam http://<카메라>:81/stream
```

`http://127.0.0.1:8090`. 방화벽은 개인 네트워크만 허용합니다.

1. 화면에 잠김 `stopped / boot`, 영상 표시. 아직 아무것도 누르지 않은 상태에서 다리가 움직이지 않음.
2. 잠금 해제 → `idle`(배터리 ≥ 6800 mV·Wi-Fi 정상일 때만, 아니면 `reset_denied`). 해제만으로 움직이지 않음.
3. 정지 버튼 → 계속 정지.
4. 비상 정지 → `stopped / estop`, 다시 잠김. 해제 후 진행.
5. 짧은 이동: 보폭 20·회전 5로 전진·후진·좌·우를 **누르는 동안만**, 놓으면 정지. 방향·쏠림·정지 지연을 기록.
6. 노트북 핫스팟을 잠깐 끊음 → 로봇이 600 ms 안에 스스로 멈추고 `link_lost` 래치. Wi-Fi가 돌아와도 사람이 해제하기 전까지 잠김 유지.
7. 동작 그룹 중 ESTOP·`stop_action`이 바로 멈추는지, 저전압 임계는 [확인 필요]. Arduino 판은 그룹이 끝난 뒤 멈춤([firmware.md](firmware.md) 4.3).
8. 바닥 주행은 위가 모두 정상이고 사용자가 범위를 정한 뒤에만.

## 3. LiDAR USB 확인 (동결 기능, 표시 확인만)

키트 USB 어댑터로 노트북에 직접 연결합니다([lidar-frozen.md](lidar-frozen.md)). `pyserial` 환경은 [dashboard.md](dashboard.md) 2절.

```cmd
.private\lidar-pc\Scripts\python.exe -m dashboard.lidar.probe --usb COM번호
.private\lidar-pc\Scripts\python.exe -m dashboard.server --lidar-usb COM번호
```

- probe: 모델·펌웨어, 상태 Good(0), 연속 스캔 3회 뒤 STOP·포트 닫힘. 끝나면 모터가 멈추는지 육안 확인.
- 대시보드: 12 m 원 위에 점, 장애물을 옮기면 점이 따라 움직임. 각도는 센서 원시 기준이라 로봇 정면과 맞는지 따로 기록.
- probe와 대시보드는 같은 COM 포트를 동시에 열지 않습니다. J5 → Wi-Fi 중계(`--relay-lidar`)는 실물 미검증이며 이 절차에 넣지 않습니다.

## 4. 결과 양식

로봇마다 하나씩 복사해 씁니다. 결과는 합격 / 실패 / 미실행 / 측정 불가.

```text
대상 ID: A / B      날짜:      작업자 별칭:      승인 범위:
펌웨어: 메인(MicroPython / Arduino)   카메라(버전, 센서, encoder)
백업: 메인 완료/미완료   카메라 완료/미완료
카메라: /status(robot, camera.ok, 해상도) / fps / frame_age_ms / RSSI:
업로드: 예외 없음 / boot 래치 / 배터리 mV:
대시보드: 해제 / 정지 / ESTOP / 전진 / 후진 / 좌 / 우 (방향·정지 지연):
링크 끊김: 정지 시간 / link_lost 래치 유지:
LiDAR USB: 상태 / 스캔 수 / 화면 점 / 모터 정지:
미통과·미실행 항목:
이상 발생과 중단 조치:
다음 단계 승인: 없음 / 별도 명시
```
