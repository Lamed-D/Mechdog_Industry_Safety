# LiDAR (동결)

> **동결: 대시보드 표시 시연 수준으로 유지. 코드 수정·추가 개발 금지(버그로 테스트가 깨질 때만 최소 수정). 지도는 앞으로 VSLAM.**
>
> 대상 코드: `custom_sensors/lidar_bridge.py`, `host/lidar/`, `ros2/`, `host/map_review.py`, `dashboard/lidar.py`, `test_PC/lidar_probe.py`.
> 이 문서는 현재 상태를 기록할 뿐 계획이 아닙니다. 아래 "계획·후보"로 적힌 것(SLAM, 지도 편집, 순찰)은 진행하지 않습니다.

관련: [hardware.md](hardware.md)(배선·전원·부품), [protocol.md](protocol.md) 7절(TCP 20108 원시 중계), [dashboard.md](dashboard.md)(LiDAR 점 표시)

## 1. 구성 요약

| 항목 | 내용 |
| --- | --- |
| 센서 | Slamtec RPLIDAR A1M8-R6, 360° 2D, 측정 약 0.15~12 m(흰색 대상 기준), 로봇 등 위에 테이프 고정 |
| UART | **115200 bps 8N1 고정**(공개 데이터시트). 더 빠른 속도는 이 센서에 해당 없음 |
| 로봇 쪽 | 별도 ESP32 없이 메인 ESP32(클래식)의 J5(IO32 = RX, IO33 = TX)를 `machine.UART(1, …, rxbuf=4096)`로 열어 **원시 바이트를 TCP 20108로 양방향 중계**. 해석 없음, 로봇을 움직이지 않음, 안전 래치와 무관 |
| 모터 | CTRL_MOTO를 5V에 묶어 상시 회전(J5 두 핀을 UART에 다 써서 모터 제어 GPIO 없음) |
| 전원 | 1단계는 라이다 전용 별도 5V(1 A 이상, 기동 최대 약 0.7 A). 상세는 [hardware.md](hardware.md) |
| 노트북 쪽 | Python 표준 라이브러리로 표준 스캔 파싱(`host/lidar/`) → 대시보드 점 표시. ROS 2 `/scan` 노드(`ros2/scan_node.py`)는 합성 시험만 |

설계 판단 근거(요약):

- J5 IO32/IO33은 서보·I2C·부저·LED·버튼·배터리·REPL과 겹치지 않는 유일한 빈 범용 GPIO입니다. J5에 터치·조도 센서를 같이 쓰지 않습니다.
- UART0은 REPL, UART2 기본 핀은 서보 5·6이 쓰므로 UART1을 IO32/IO33에 지정합니다. 순정 MicroPython v1.21.0의 `machine.UART`가 `baudrate/tx/rx/txbuf/rxbuf/timeout`을 받는 것은 펌웨어 문자열로 확인, 실제 동작은 루프백으로 확인 필요.
- 공식 `Hiwonder.UART`는 `CMD~$` 텍스트용이라 바이너리 중계 불가 → `machine.UART` 사용(추가 센서 읽기 예외).
- 서보 출력은 순정 펌웨어의 C 타이머가 갱신하므로 중계가 걸음에 주는 영향은 작을 것으로 **예상**. 걸음 궤적 계산이 C인지는 확인 필요.
- I2C→UART 변환칩(SC16IS750)은 쓰지 않습니다(부품 추가, 비전 모듈 버스 간섭, 자체 드라이버 필요).
- 라이다 스트림은 TCP(순서 보장), 명령·상태는 UDP 9100/9101.

## 2. 로봇 중계 (`custom_sensors/lidar_bridge.py`)

규칙 전체는 [protocol.md](protocol.md) 7절. 요점:

- 한 번에 클라이언트 하나, 새 연결이 오면 기존 연결 교체. 클라이언트가 없으면 UART 바이트를 읽어 버림(`drained`).
- TCP가 밀리면 UART 버퍼가 넘쳐 바이트를 잃을 수 있고, 노트북 파서가 경계를 다시 찾습니다.
- UART 수위 75% 이상 또는 미송신 묶음 100 ms 이상이면 TEL `lidar_backlog`(임계는 가정). 호스트는 경고 중 새 `MOVE`를 막습니다. UART를 못 열면 `lidar_uart`.
- `LidarBridge.metrics()`: REPL 읽기용 진단(수위, 미송신 바이트·나이, 총 바이트, 버린 바이트, 송신 정체 횟수, bytes/s). 하드웨어 오버런 손실은 세지 못함.

## 3. 노트북 수신 (`host/lidar/`)

표준 라이브러리만 사용하며 import만으로 네트워크에 연결하지 않습니다.

| 파일 | 내용 |
| --- | --- |
| `rplidar_protocol.py` | 요청, 7바이트 디스크립터, **표준 스캔 5바이트 샘플**과 분할 수신 처리. 고속·압축 스캔 모드는 범위 밖 |
| `scan_assembler.py` | 시작 플래그 사이를 한 회전으로 묶음. 첫 부분 회전과 종료 시 미완성 회전은 버림. 거리 mm, 각도 도, 수신 순서 유지. 장착각·방향은 생성자 설정. 거리 0은 "장애물 없음"이 아니라 **측정 무효**(품질과 함께 보존) |
| `tcp_client.py` | STOP → 100 ms 대기 → GET_HEALTH → SCAN 순서로 시작. 건강 상태 0·1만 허용, 오류·모르는 상태면 스캔 시작 안 함. `session()`은 실패를 예외로, `run()`은 실패 콜백 후 재접속(콜백에서 `ScanAssembler.reset()`). 중단 시 `close()`로 STOP 전송·소켓 닫기 보장 |
| `laser_scan.py` | 회전 → 각도별 거리(m) 배열(대시보드가 사용) |

- 표준 샘플에는 체크섬이 없습니다. 시작/반전 비트·check 비트·각도 범위를 검사하고 한 바이트씩 밀며 동기를 회복하지만, 정상처럼 보이는 손상은 못 잡습니다.
  회전 결과는 모든 점의 무결성이나 360° 완전성을 보증하지 않습니다.
- 거리 0, 낮은 품질, 150 mm 미만·12000 mm 초과를 정상 관측으로 보지 않고, 경계 거리의 실제 장애물로 바꾸지도 않습니다. 안전 판단에 쓰려면 무효·범위·신선도 검사가 따로 필요합니다.
- 각도 인코딩 정밀도 1/64°와 센서의 실제 각도 해상도 약 1°는 다른 개념입니다.
- 전송량 한계: 115200 bps 8N1 → 최대 11520 B/s → 표준 샘플만이면 **2304 점/초**. 데이터시트의 8000회/초를 이 경로의 전송량으로 쓰면 안 됩니다.
- 회전 약 5.5 Hz(5V 모터, 명목값, 실측 전).
- 명령·디스크립터·샘플 배치는 제조사 공개 SDK(BSD 2-Clause)로 비트 배치만 확인해 독립 구현했습니다. SDK 코드를 복사하거나 의존성으로 넣지 않았습니다.

## 4. ROS 2 (`ros2/`, 합성 시험만)

WSL 2 Ubuntu 24.04 + ROS 2 Jazzy 실제 실행은 **미검증**입니다. ROS는 선택 의존성(`ros-jazzy-sensor-msgs`)입니다.

```bash
source /opt/ros/jazzy/setup.bash
export ROS_DOMAIN_ID=42 ROS_LOCALHOST_ONLY=1
python -m ros2.scan_node --robot A --host <로봇 IP> --port 20108
ros2 topic hz /robot_a/scan
```

- `scan_node.py`: `/robot_<id>/scan` LaserScan 발행. 정면 0·반시계 양수인 ROS 기준으로 변환, 기본 `--direction -1`, 장착 정면은 `--offset-deg`로 교정(실물 미교정).
  거리 0·품질 0·범위 밖·빈 각도는 NaN(빈 공간으로 해석 금지). 재연결 때 부분 회전 폐기, 최대 2프레임 보관, 300 ms 넘게 대기한 프레임 폐기.
  하드웨어 타임스탬프가 없어 첫 빔 시각은 수신 시각 기반 추정, `time_increment=0`. 건강 Warning은 로그, Error면 재시도 중단(자동 RESET 없음). 종료 시 라이다 STOP 시도, 로봇 이동 명령 없음.
  TF·odometry·SLAM은 만들지 않습니다.
- `map_grid.py`: `from_occupancy_grid(message)`가 ROS OccupancyGrid를 `host/map_review.py`의 Grid로 변환(순수 함수, 구독 없음).

## 5. 지도 편집 검사 (`host/map_review.py`, 순수 함수)

동결 전 "LiDAR SLAM 초안 → 사람 검토·확정 → 구역 지정 → 순찰"을 위해 만든 검사 함수입니다. 어떤 실행 경로에도 연결돼 있지 않습니다.

- 입력: 너비·높이·m/cell·원점 `(x, y, yaw)`(첫 셀 왼쪽 아래)·좌표계·행 우선 셀 배열(최대 1,000,000, 생성 시 복사).
- 셀 의미(보수적): **0만 빈 공간**, -1 미확인, 1..100 모두 막힘.
- `review_edit(base, proposal)`: 크기·해상도·원점·좌표계가 다르면 거절. **미확인 → 빈 공간은 승인이 있어도 거절.** 장애물 → 빈 공간은 셀마다 표시해 사람 승인 필요. 장애물 추가·미확인으로 막기는 승인 불필요.
- `approve_edit`: 검토 당시 초안·제안의 SHA-256과 삭제 셀 승인 목록을 다시 대조, 하나라도 다르면 재검토. 인덱스 → `(index % width, index // width)`.
- 해시는 무결성 대조값이지 인증이 아닙니다. 통과해도 계단·지도 밖 위험·위치 추정·제동 여유는 검증되지 않습니다.
- ROS 입력 제한: 평면 전용. 원점 z, 쿼터니언 x/y, norm²−1에 1e-6 허용오차를 넘으면 거절(자동 보정 없음). -1은 유지.

## 6. 검증 상태

| 경로 | 상태 |
| --- | --- |
| A1M8 → USB → Windows (`test_PC.lidar_probe --usb`, 대시보드 `--lidar-usb`) | 장치 응답, 상태 0, 연속 스캔 3회, STOP·포트 닫기 확인. 대시보드 점 표시 확인. 모터 정지 육안·거리 정확도는 미확인 |
| A1M8 → J5 UART → Wi-Fi → Windows | **실물 미검증**(J5 루프백, GET_INFO 응답, 무선 부하, 보행 중 걸음 품질 포함) |
| ROS 2 `/scan`, SLAM, TF, 오도메트리 | 미검증(SLAM은 진행하지 않음) |

남은 하드웨어 확인 항목(보드 회로도 버전, J5 1번 핀·커넥터 형번, 라이다 커넥터 핀 방향, 5V 레일 여유, 실측 전류)은 [hardware.md](hardware.md)에서 관리합니다.

## 7. 진행하지 않는 것 (VSLAM으로 대체)

동결 전 계획이던 아래 항목은 **진행하지 않습니다.** 지도·위치 추정은 앞으로 VSLAM으로 새로 설계합니다([scenario.md](scenario.md)).

- LiDAR 기반 SLAM(레이저 오도메트리 후보), 위치 추정·경로 계획, 자동 정찰
- 지도 초안 → 사람 검토·확정 → 구역·지점·경로 지정 → 순찰 루틴
- (참고로 남길 교훈) 공식 API에 오도메트리가 없고, 걷는 진동과 테이프 고정 때문에 바퀴 로봇보다 스캔 정합이 나쁠 수 있습니다. 실제 현장 지도는 커밋하지 않고 테스트에는 코드로 만든 합성 지도만 씁니다.
