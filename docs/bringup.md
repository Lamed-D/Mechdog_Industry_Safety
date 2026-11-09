# 실물 확인 절차 (부품 도착 후)

[라이다 연동 설계](lidar-integration.md) 10절 1~5단계와 [통신 규약](protocol.md)의 **[확인 필요]** 항목을
사람이 순서대로 따라 할 수 있게 정리했습니다. 스크립트는 `tools/bringup/`에 있습니다.

- **로봇을 움직이는 단계는 없습니다.** 그래도 장치에 올리거나 실행하는 일은 사용자 확인 후에, 확인받은 로봇(A/B)에만 합니다.
- 장치에 있는 기존 `main.py`를 덮어쓰지 않습니다. 스크립트는 REPL에 붙여 넣거나 Python Editor에서 실행만 합니다.
- 결과 칸에는 **실제로 잰 값만** 적습니다. 못 쟀으면 비워 둡니다. 영상·사진에 사람 얼굴이 나오지 않게 합니다.
- 라이다 값(115200 bps 8N1, 3.3 V TTL, 코어 5V 300~350 mA·켜질 때 최대 600 mA, 모터 5V 약 100 mA)은 공개 데이터시트 기준입니다.

## 준비물

| 항목 | 비고 |
| --- | --- |
| 멀티미터 | J5 전압·라이다 전류 |
| 점퍼선 암-암 | 루프백(J5-3 ↔ J5-4), 라이다 연결 |
| 별도 5V 전원(2A 이상) | 1단계 라이다 전원. J5-1(5V)은 쓰지 않음 |
| 전용 공유기(2.4 GHz), PC 또는 Pi 5 | Wi-Fi 지연 측정 |

## 단계

| # | 할 일 | 스크립트 | 정상 결과 | 실패하면 확인 |
| --- | --- | --- | --- | --- |
| 0 | J5 전압: 전원 켜고 아무것도 연결하지 않은 채 J5-1·J5-2 측정 | — | J5-1 ≈ 5 V, J5-2 = 0 V | 1번 핀 위치, 보드 버전 |
| 1 | 펌웨어·API 확인 | `b1_board_info.py` (장치) | 모든 줄 `OK`. 특히 `MechDog.action_is_over`, `MechDog.stop_action`, `network.WLAN.PM_NONE`, `machine.UART(1, …, rx=32, tx=33, rxbuf=4096)` | `FAIL` 줄을 이슈로 올림. UART 키워드가 안 되면 `rxbuf` 없이, UART 번호 2로 다시 시험 |
| 2 | J5 루프백: J5-3(IO33)과 J5-4(IO32)를 점퍼로 연결, 라이다는 뺌 | `b2_uart_loopback.py` (장치) | `sent 256 got 256 match True` | 점퍼 위치, UART 번호·핀 |
| 3 | 라이다 단독: 키트 USB 어댑터로 PC에서 먼저 회전·데이터 확인 | (제조사 PC 도구) | 모터 회전, 점이 보임 | 케이블 방향, 전원 |
| 4 | 라이다 전류: 별도 5V로 코어·모터 전원, 모터 제어선은 5V에 연결 | — | 켜질 때·회전 중 전류(데이터시트 합계 약 0.4~0.7 A) | 극성, 커넥터 1번 핀 |
| 5 | 라이다 ↔ J5: 라이다 TX → J5-4, RX → J5-3, GND 공통 | `b3_lidar_info.py` (장치) | `health: ('Good', 0)`, `info: {...}` | 응답이 없으면 TX/RX를 바꿔 다시(방향 **[확인 필요]**), GND 공통 |
| 6 | Wi-Fi 접속·지연: 로봇에서 echo 실행 → PC/Pi 5에서 측정 | `b4_wifi_echo.py` (장치, `secrets.py` 함께), `rtt_probe.py` (PC/Pi 5) | 접속 OK, `p99_ms`가 600보다 충분히 작고 `gaps_over_timeout` 0 | 2.4 GHz 여부, PM_NONE 지원, 거리·장애물 |
| 7 | 비전 모듈 영상 | `camera_check.py <URL>` (PC/Pi 5) | 상태 200, 초당 프레임 수가 0보다 큼 | 영상 주소·포트(**[확인 필요]**), 5V 2A 전원 |

## 결과 기록

로봇마다 한 번씩 적습니다. 날짜와 측정한 사람(역할)만 적고, 개인정보는 적지 않습니다.

| 항목 | 로봇 A | 로봇 B |
| --- | --- | --- |
| 날짜 | | |
| `sys.version` / `sys.implementation` | | |
| 보드 회로도 버전(V1.0/V1.2), J5 1번 핀 위치 | | |
| `action_is_over` / `stop_action` 있음 | | |
| `PM_NONE` 지원 | | |
| UART 열기 성공한 형태 | | |
| 루프백 결과 | | |
| 라이다 TX/RX 방향(IO32=RX 맞는지) | | |
| 라이다 health / model / firmware | | |
| 라이다 전류(켜질 때 / 회전 중) | | |
| Wi-Fi RTT p50 / p95 / p99 / max (PM_NONE 켬) | | |
| Wi-Fi RTT p99 (PM_NONE 끔) | | |
| 가장 긴 응답 공백, 600 ms 넘은 횟수 | | |
| 비전 모듈 영상 주소, fps | | |

## 결과를 반영할 곳

| 결과 | 고칠 곳 |
| --- | --- |
| UART 번호·키워드, TX/RX 방향 | `robot/config.py`, [통신 규약](protocol.md) 7절, [라이다 연동 설계](lidar-integration.md) 4절 |
| RTT | `LINK_TIMEOUT_MS`·`MOVE_HOLD_MS`(protocol.md 5.1절, 8절) |
| `action_is_over`/`stop_action` | [MechDog 제어 API 규칙](dev/mechdog-api.md) 5절 (공용 문서: 승인 후) |
| PM_NONE | protocol.md 6.1절 `pm_on` |
| 영상 주소 | [시연 시나리오](demo-scenario.md) 8절 |

## 다음 확인 (로봇이 움직임 — 사용자 확인 후, 줄로 묶은 상태)

이 문서 범위 밖입니다. `robot/` 펌웨어를 올린 뒤 할 일만 적어 둡니다: 동작 그룹 중 `stop_action()`·`move(0, 0)`이 바로 멈추는지,
동작별 소요 시간(`ACTION_DURATION_MS`), 저전압 임계, 보행 중 라이다 중계와 걸음 품질(설계 문서 10절 10단계).
