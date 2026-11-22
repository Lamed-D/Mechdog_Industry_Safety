# Windows 노트북 시험

저장소 최상위에서 CMD로 실행합니다. 합성 시험은 Python 표준 라이브러리를 사용하며 실제 장비에 명령을 보내지 않습니다.

```cmd
test_PC\run.cmd robot
test_PC\run.cmd dashboard
test_PC\run.cmd console
test_PC\run.cmd lidar
test_PC\run.cmd integration
test_PC\run.cmd all
python tools\check_confidential.py range origin/main..HEAD
```

카메라·조작·LiDAR 그래프를 함께 검증하는 모의 및 실물 절차는 [PC 조종 콘솔](robot_console/README.md)에 있습니다.
기본 영상 Wi‑Fi와 두 대 공통 로봇망 연결은 [ESP32-S3 카메라 연결 안내](camera-setup.md)를 따릅니다.

통합 시험은 A/B를 번갈아 발견 로봇으로 사용해 합성 낙상 이벤트, 대시보드 알림, 반대쪽 로봇의 관리자 호출·사고 지점 안내, 링크 손실 시 정지와 자동 재개 방지를 확인합니다. 본체 watchdog과 역할 인수 테스트는 별도로 가짜 본체의 정지 래치를 확인합니다.

```cmd
python -m tools.mock.demo_scenario --finder B --fault link
python -m dashboard.web.run --sim
```

두 번째 명령의 화면은 `http://127.0.0.1:8000`입니다. TCP 스캔의 모의 왕복을 확인하려면 두 CMD 창에서 다음 명령을 한 줄씩 실행합니다. 첫 번째 창은 Ctrl+C로 끝냅니다.

```cmd
python -m tools.mock.mock_lidar
python -m test_PC.lidar_probe --tcp 127.0.0.1
```

## 장비 시험

| 경로 | 실행 및 판정 | 검증 상태 |
| --- | --- | --- |
| A1M8 → USB → Windows | 확인한 A1M8 어댑터 COM 포트로 아래 USB 명령을 실행합니다. 장치 정보·상태·회전별 샘플 수와 STOP/포트 종료를 확인합니다. | 노트북에서 장치 응답, 상태 0, 연속 스캔 3회, STOP 전송 및 포트 닫기 확인. 모터 정지 육안 확인과 거리 정확도는 별도입니다. |
| A1M8 → MechDog J5 UART → Wi-Fi → Windows | 사용자 장비 시험에서 해당 본체 IP를 `--tcp`로 지정합니다. TCP 20108에서 상태·회전별 스캔을 확인하고 A/B를 각각 검증합니다. | 동일 클라이언트의 합성 TCP 시험 완료. J5, 무선 구간, 두 대 동시 수신은 실물 미검증입니다. |
| 본체 A/B → UDP → Windows 대시보드 | [호스트 실행 안내](../docs/host-setup.md)의 정지형 모드에서 ID·상태·정지를 확인합니다. | 사용자 로봇 동작·카메라 시험 결과는 [후속 계획](../docs/host-setup.md)에 반영했습니다. |

```cmd
python -m venv .private\lidar-pc
.private\lidar-pc\Scripts\python.exe -m pip install pyserial
.private\lidar-pc\Scripts\python.exe -m test_PC.lidar_probe --usb COM번호
```

USB 시험은 라이다 모터를 구동합니다. 확인한 라이다 전용 어댑터를 사용합니다. 본체 Wi-Fi 경로는 본체와 카메라가 같은 로봇망에 접속한 상태에서 별도로 시험합니다. 실제 로봇 이동과 펌웨어 업로드는 사용자 승인 범위에서 진행합니다.
