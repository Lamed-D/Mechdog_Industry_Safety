# 실물 로봇 시험

사람이 실제 장비에서 따라 하는 점검 순서와 결과 양식입니다. 현재 장비는 **MechDog 1대 + 앞쪽 ESP32-S3 비전 모듈 + 등 위 RPLIDAR A1M8 + Windows 노트북 1대**입니다. 시험과 기록은 로봇 단위(ID A/B)로 합니다.

## 0. 공통 원칙

- **장치 업로드·굽기·전원·구동은 사람만** 합니다. 에이전트는 합성 시험·코드 검토·전달 폴더 생성까지만 합니다. 컴파일·가짜 모듈 통과로 실물 합격을 대신하지 않습니다.
- 실행 승인에는 **대상 ID, 스크립트, 시험 범위**를 적습니다. 읽기 점검이 끝나도 업로드·이동 승인은 자동으로 생기지 않습니다.
- 기존 `main.py`를 덮어쓰지 않고 이름도 바꾸지 않습니다. 시험 파일은 편집기에서 **Download만**(Download and Run·Reset·빈 REPL에서 Ctrl+D 금지: 기존 main의 모션 초기화가 돌 수 있음). raw REPL이면 Ctrl+B.
- 메인 보드 COM(이전 기록 COM6)과 카메라 COM(CH340)을 구분합니다. 번호는 재연결 때 다시 확인합니다.
- 첫 시험은 적재물 없이 받침대 위. 손으로 다리를 붙들지 않습니다. 바닥 주행은 빈 공간과 즉시 전원 차단 수단을 확보한 뒤.
- 발열·냄새·부팅 반복·예상치 못한 움직임·정지 실패면 **즉시 중단하고 전원 차단**, 다음 항목으로 넘어가지 않습니다.
- 결과에는 실제로 잰 값만. `미실행`, `실패`, `측정 불가`를 그대로 적습니다. 얼굴·현장 영상, 비밀번호·키, 장치 일련번호, 개인정보는 남기지 않습니다(작업자는 별칭).
- 백업·업로드·복구 절차는 [firmware.md](firmware.md), 배선·전원은 [hardware.md](hardware.md), 메시지는 [protocol.md](protocol.md).

## 1. 스크립트 (`tools/bringup/`)

모두 로봇을 움직이지 않습니다. 예외는 `robot_motion_check.py`(명시적 인자로만 움직임).

| 파일 | 실행 위치 | 하는 일 |
| --- | --- | --- |
| `mechdog_only.py` | 메인 REPL `main()` | 공식 API 존재·배터리 mV. MechDog 객체를 만들지 않음 |
| `api_candidates.py` | 메인 REPL `main()` | 문서 밖 후보(`run_status`, `read_servo`, `set_offset` 등) **존재만** 확인, 호출 금지 |
| `robot_imu_check.py` | 메인 REPL `print(run())` | 공식 I2C IMU 각도·형식·호출 시간 |
| `robot_loop_check.py` | 메인 REPL | `Hiwonder.startMain` 4개 루프 등록·양보 |
| `vision_probe.py` | 메인 REPL | 공식 카메라 I2C 읽기(단독 파일, `Hiwonder_IIC`·`time`만 import) |
| `vision_official.py` | 메인 REPL | `robot/vision.py`를 `vision.py`로 올린 뒤 공식 경로 확인 |
| `robot_motion_check.py` | 메인 REPL | 정지·짧은 이동·동작 그룹 1항목씩. 배터리 하한 7000 mV [가정] |
| `b1_board_info.py` | 메인 REPL | 펌웨어·모듈·`PM_NONE`·UART 키워드 지원 |
| `b2_uart_loopback.py` | 메인 REPL | J5 UART 루프백 |
| `b3_lidar_info.py` | 메인 REPL | 라이다 STOP→GET_HEALTH→GET_INFO |
| `b4_wifi_echo.py` + `rtt_probe.py` | 메인 REPL(`secrets.py` 필요) / PC | UDP 왕복 지연 `python tools/bringup/rtt_probe.py <로봇IP> [--count 300] [--port 9100]` |
| `camera_check.py` | PC | 영상 URL 응답·바이트 수 `python tools/bringup/camera_check.py <URL> [--seconds 5]` |

**전달 폴더(PC만):** `python tools/package_robot_checks.py` → `build/robot_checks/`(시험 `.py` 6개 + 안내·체크리스트·빈 양식 + 해시 명세). `--verify`로 누락·변경 검사. 보드에는 `mechdog_only`, `api_candidates`, `robot_imu_check`, `robot_loop_check`, `vision_probe`, `robot_motion_check` 6개만 원래 이름으로 올립니다. `tests/fakes/`, 호스트 코드, 통합 main, secrets 예시는 시험 업로드 대상이 아닙니다.

## 2. 점검 순서

한 단계가 정상일 때만 다음으로 갑니다.

| # | 단계 | 정상 결과 | 실패 시 |
| --- | --- | --- | --- |
| 1 | PC: `python -m unittest discover -s tests`, 가짜 본체 `python -m dashboard.fake_robot` + `python -m dashboard.server` | 통과, 화면에 boot 잠금·합성 영상 | 코드·환경. 실물 연결 안 함 |
| 2 | 외관·고정·배선·배터리, 라이다 고정·0° 방향 (전원 OFF) | 손상·느슨함 없음 | 고정 후 재확인 |
| 3 | 백업 확인: 메인 `main.py`·설정, 카메라 플래시 전체 | 대상별 백업·해시 | 백업 없으면 중단 |
| 4 | 카메라 펌웨어 굽기·설정·영상 확인 ([firmware.md](firmware.md) 6.5) | `/status` ID·`camera.ok`·STA, `/capture`, `:81/stream`, 창 닫고 다시 열어도 새 영상 | 다음 단계로 가지 않고 백업으로 복구 |
| 5 | 본체 읽기·루프 (3절 A) | 표의 정상 관측 | 결과 보고, main 적용 보류 |
| 6 | 본체 동작 1항목씩 (3절 B) | 실제 방향·정지 확인 | 전원 차단, 백업 복구 |
| 7 | 통합 main 업로드 ([firmware.md](firmware.md) 2.2) | 예외 없음, boot 래치·정지 TEL | 자동 실행 중단, 기존 main 복원 |
| 8 | PC 화면 연결 후 정지 시험 (4절) | ESTOP·600 ms 단절·저전압/예외에서 정지 | 원인 확인 전 재개 금지 |
| 9 | 라이다 J5 경로 (5절, 동결 기능이라 표시 확인만) | health Good, 화면에 점 | 극성·공통 GND·TX/RX·전원 |

## 3. 본체 Python 점검 (통합 main 적용 전 필수)

근거는 공식 Python 문서와 제조사 예제의 호출·인자입니다. 장치의 실제 라이브러리 소스는 찾지 못했고(frozen 가능), 실제 구현 대조는 **미완료**입니다. 이동 ±20 / 회전 ±5 / 300 ms, 동작 완료 대기 3초, 배터리 7000 mV는 공식 범위 안의 **초기 시험값·가정**이며 거리·정지 시간을 보장하지 않습니다.

### A. 읽기·루프 (움직이지 않음)

| 항목 | 실행 | 정상 관측 |
| --- | --- | --- |
| API·배터리 | `import mechdog_only; mechdog_only.main()` | 필요한 API가 true, 또는 실물 `MechDog`가 팩토리 함수(`mechdog_kind: factory`)라 null(정상). 배터리 양의 정수 mV. NA나 false면 중단·보고 |
| 후보 API | `import api_candidates; api_candidates.main()` | 존재 여부만 기록. 보정·서보 후보는 절대 호출 안 함 |
| IMU | `import robot_imu_check; print(robot_imu_check.run())` | angles·형식·호출 시간. 단위·칩은 별도 확인 |
| 4개 루프 | 아래 코드 | counts=[50,50,50,50], done 모두 True, errors·registration_error 없음, REPL 응답 유지, `registration_elapsed_ms` 기록 |
| 카메라 I2C | `import vision_probe; vision_probe.main()` | 5절 표 |

```python
import robot_loop_check as loops
import time
state = loops.run(allow_background=True)
time.sleep_ms(1000)
print(state)
```

**통합 main은 `startMain` 4개 동시 등록을 쓰므로 루프 항목 확인 전에는 실물 적용을 보류합니다.** 등록 호출이 루프 완료(약 500 ms)까지 기다렸다면 동시 실행을 확인한 것이 아닙니다.

### B. 동작 (항목마다 별도 승인)

`robot_motion_check.py`는 import·Download만으로 움직이지 않습니다. `MechDog()` 생성 자체도 관측 대상입니다. 첫 항목은 반드시 stop, 여섯 항목을 연속 실행하는 코드를 만들지 않습니다.

```python
import robot_motion_check as checks
print(checks.run("stop", allow_motion=True))
# 확인 후 별도 승인한 항목 하나만: "forward" | "backward" | "left" | "right" | "action"
```

| case | 관측할 것 | 실패 기준 |
| --- | --- | --- |
| stop | 초기화 직후 보행 없음, 정지 유지 | 예상치 못한 움직임 |
| forward / backward | 방향·쏠림·300 ms 뒤 정지 지연, 뒤 공간 | 반대 방향, 불안정, 계속 이동 |
| left / right | 작은 전진 + 회전(제자리 회전 아님)·정지 | 방향·보폭 의미 불일치 |
| action | `nodding_motion` 시작·완료 반환과 실제 종료 일치 | 3초 대기 초과, 반환 불일치 |

- 완료·예외·Ctrl+C 경로에서 `stop_action`과 `move(0, 0)`을 각각 시도합니다. 낮거나 알 수 없는 배터리면 시작하지 않습니다.
- `calls_completed`는 API 호출 완료일 뿐 합격이 아닙니다. 방향·쏠림·정지 지연·이상음·접촉은 사람이 기록합니다.
- 공식 호출이 막히거나 전원이 불안정하면 소프트웨어 시간 제한·정지 호출이 제때 실행되지 않을 수 있습니다.
- 단독 동작 시험은 통합 통신 끊김 안전 시험(4절)을 대신하지 않습니다.

## 4. 통합 main + PC 화면 안전 점검 (받침대)

PC: `python -m dashboard.server --robot <ID> --robot-ip <IP|auto> --allow-real --cam http://<카메라>:81/stream [--relay-lidar]` → `http://127.0.0.1:8090` ([dashboard.md](dashboard.md)). 방화벽 개인 네트워크 허용.

1. 잠김 상태 `stopped / boot`, 영상 표시.
2. 해제 버튼 → `idle` (배터리 ≥ 6800 mV·Wi-Fi 정상이어야 해제, 아니면 `reset_denied`).
3. 비상 정지 → `stopped / estop`. 해제 후 진행.
4. 누르는 동안만 전진·후진·좌·우, 놓으면 정지.
5. 노트북 핫스팟을 잠깐 끊음 → 로봇이 스스로 멈추고 `link_lost` 래치. Wi-Fi 복구 후에도 래치 유지.
6. 동작 그룹 중 ESTOP·`stop_action`이 바로 멈추는지, 동작별 소요 시간, 저전압 임계 [확인 필요]. Arduino 판은 그룹이 끝난 뒤 멈춤([firmware.md](firmware.md) 4.3).
7. 바닥 주행은 위가 모두 정상이고 사용자가 범위를 정한 뒤에만.

## 5. 카메라 I2C·영상 판정

메인 보드에서 본 카메라는 물리 **IIC 포트 1** = Python `Hiwonder_IIC.IIC(2)` + `Hiwonder_IIC.ESP32S3Cam`. `read_face()`가 있으면 우선 쓰고(진단 버전 2가 `VISION_METHOD_SELECTED`로 표시), 없을 때만 `face_recognition()`. 실패를 숨기려 다른 메서드를 자동 재시도하지 않습니다. 출력은 `VISION_ONLY_BEGIN` / `VISION_RESULT` / `VISION_ONLY_END`.

| 결과 | 해석 |
| --- | --- |
| `observed`, `has_result=False` | 정상 응답. **맞춤 영상 펌웨어의 기대값**(인식 결과 없음 고정 응답) |
| `observed`, `has_result=True` | 인식 결과 있음. 낙상·사람 감지 검증 아님 |
| `unknown`, stage `face_read`, errno 19 | 읽기 실패. 기능 모드·케이블·전원 확인. 무작정 재플래시·raw I2C·주소 스캔 금지. 맞춤 펌웨어면 I2C 주소(0x53/0x52) 확인 |
| stage `iic_init` / `camera_init` | 버스 생성 / 카메라 객체 생성 실패 |
| `camera_api_missing` | 메인 보드 라이브러리 지원 확인 필요 |
| `IndentationError` | 파일·붙여넣기 손상. 하드웨어 문제 아님 |

- 생성자 성공만으로 장치 응답을 확인했다고 보지 않습니다. OSError만으로 고장·배선 오류를 확정하지 않습니다.
- 기록: 로봇 B + 맞춤 펌웨어 v0.1.7에서 `observed`, `has_result: False`, `read_ms: 2`. 그 전 제조사 펌웨어 상태에서는 `face_read` errno 19.
- 영상 판정은 PC에서: `/status` 값과 fps·`frame_age_ms`·RSSI 숫자만 기록. 영상 없음은 "사람 없음"이 아니라 `unknown`.

## 6. 라이다 J5 점검 (기능 동결, 참고용)

라이다는 대시보드 표시 시연만 하고 더 개발하지 않습니다([lidar-frozen.md](lidar-frozen.md)). 값은 공개 데이터시트 기준(115200 bps 8N1, 3.3 V TTL, 코어 5 V 300~350 mA·기동 최대 600 mA, 모터 5 V 약 100 mA).

| # | 할 일 | 정상 결과 | 실패 시 |
| --- | --- | --- | --- |
| 0 | 아무것도 연결 안 하고 J5-1·J5-2 전압 | J5-1 ≈ 5 V, J5-2 = 0 V | 1번 핀 위치, 보드 버전 |
| 1 | `b1_board_info.py` | 모든 줄 OK(`action_is_over`, `stop_action`, `PM_NONE`, `UART(1, …, rx=32, tx=33, rxbuf=4096)`) | UART 키워드가 안 되면 `rxbuf` 없이, UART 2로 |
| 2 | J5-3(IO33)↔J5-4(IO32) 점퍼, 라이다 뺌, `b2_uart_loopback.py` | `sent 256 got 256 match True` | 점퍼·UART 번호 |
| 3 | 키트 USB 어댑터로 PC 단독 확인 | 모터 회전, 점 표시 | 케이블·전원 |
| 4 | 별도 5 V(2 A 이상, J5-1 안 씀)로 전류 측정 | 합계 약 0.4~0.7 A | 극성, 1번 핀 |
| 5 | 라이다 TX→J5-4, RX→J5-3, GND 공통, `b3_lidar_info.py` | `health: ('Good', 0)`, `info` | TX/RX 바꿔 재시험(방향 [확인 필요]) |
| 6 | `b4_wifi_echo.py` + `rtt_probe.py` (PM_NONE 켬/끔 비교) | `p99_ms`가 600보다 충분히 작음, `gaps_over_timeout` 0 | 2.4 GHz, 거리·장애물 |

라이다가 끊겨도 로봇은 멈추지 않습니다. 결과는 `robot/config.py`(UART·방향), [protocol.md](protocol.md)(`LINK_TIMEOUT_MS`·`MOVE_HOLD_MS`, `pm_on`)에 반영합니다.

## 7. 결과 양식

로봇마다 하나씩 복사해 씁니다.

```text
대상 ID: A / B          날짜:          작업자 별칭:
승인 범위:
메인 보드 / 카메라 보드 구분 확인:
백업 대상·복구 위치 확인: 완료 / 미완료   시험 파일 manifest 해시: 통과 / 실패 / 미실행
펌웨어: 메인(MicroPython / Arduino, 버전)   카메라(버전, 센서, encoder)
API (move / stop_action / action_is_over):        배터리 mV:
J5 전압 / UART 형식 / 루프백:
라이다 health·모델·펌웨어(일련번호 제외) / 전류:
Wi-Fi PM_NONE / RTT p50·p95·p99·max / 600 ms 초과 횟수:
카메라 /status (robot, camera.ok, psram, 해상도) / fps / frame_age_ms / RSSI:
미통과·미실행 항목:
이상 발생과 중단 조치:
다음 단계 승인: 없음 / 별도 명시
```

| 항목 | 소프트웨어 반환 | 실제 관측·정지 지연·등록 시간 | 결과 |
| --- | --- | --- | --- |
| API·배터리 | | | 미실행 |
| IMU | | | 미실행 |
| 4개 루프 | | | 미실행 |
| 카메라 I2C | | | 미실행 |
| stop | | | 미실행 |
| forward | | | 미실행 |
| backward | | | 미실행 |
| left | | | 미실행 |
| right | | | 미실행 |
| action | | | 미실행 |
| 통합: ESTOP / 600 ms 단절 / 래치 유지 | | | 미실행 |

결과는 합격 / 실패 / 미실행 / 측정 불가로 구분합니다. 이 결과를 검토하기 전에는 통합 main 적용 승인이 없습니다.
