# Windows 노트북 호스트 실행 계획

개발·데모 기준은 Windows 노트북 한 대와 MechDog 두 대입니다. 각 본체와 카메라를 같은 2.4 GHz 로봇망에 연결하고, 노트북이 명령·상태, 영상, 라이다, 대시보드를 담당합니다. 두 대의 영상으로 낙상 감지, 라이다 기반 SLAM·위치 추정·경로 계획도 이 노트북에서 실행하는 것이 목표입니다.

## 개발 순서

1. [test_PC](../test_PC/README.md)에서 합성 시험을 먼저 실행합니다. 이어 A1M8을 노트북 USB에 연결해 장치 정보·상태·스캔·종료를 확인합니다.
2. 사용자 장비 시험에서 A/B 본체와 카메라에 서로 다른 주소를 배정합니다. 각 본체의 ID와 UDP 9100/9101, 카메라의 MJPEG 주소, 본체 LiDAR TCP 20108을 노트북에서 확인합니다. 개별 카메라 AP에서 성공한 시험과 공통 로봇망에서 두 대가 동시에 연결되는 시험을 구분합니다. 주소와 자격 정보는 로컬에 보관하고 로봇망 포트를 외부에 공개하지 않습니다.
3. 두 본체의 상태를 로컬 대시보드에서 확인하고, A/B 각각의 영상과 스캔을 올바른 ID에 연결합니다. 한 대씩 [PC 조종 콘솔](../test_PC/robot_console/README.md)에서 영상·상태·LiDAR와 정지 흐름을 확인합니다. 기존 사용자 조작·카메라 시험은 [#105](https://github.com/Lamed-D/Mechdog_Industry_Safety/pull/105)에 기록돼 있습니다.
4. 노트북에서 두 스트림의 디코딩·추론 지연, 센서 신선도, SLAM 위치 오차를 측정합니다. 확정 지도에서 관리자·사고 지점을 지정하고, 정지·잠금 해제·경로 중단 조건을 먼저 검증한 뒤 이동 실행기를 연결합니다.
5. 로컬 화면에서 낙상 알림, 관리자 호출, 안내, 완료를 연결합니다. 실측과 안전 검증을 마친 뒤 상세 지도·이력·운영 UI를 합치고, 대체된 경로는 의존을 확인한 뒤 정리합니다. 원격 클라우드 동기화는 별도 후속 범위입니다.

## Windows CMD 실행 순서

1. 저장소 최상위에서 `test_PC\run.cmd all`을 실행합니다.
2. `python -m dashboard.web.run --sim`으로 로컬 브라우저 화면을 확인합니다. `python -m tools.mock.demo_scenario --finder B --fault link`로 합성 이벤트와 링크 손실 흐름을 재현할 수 있습니다.
3. 실물 시험 승인 후 로봇별 주소로 `python -m test_PC.lidar_probe --tcp %ROBOT_A_IP%`를 실행하고 B도 반복합니다. 각 카메라 URL은 독립적으로 확인합니다.
4. 두 주소와 로컬 조작 토큰을 설정한 CMD에서 `python -m dashboard.web.run --allow-real --robot-a %ROBOT_A_IP% --robot-b %ROBOT_B_IP% --token %DASHBOARD_TOKEN%`을 실행합니다. 한 프로세스가 두 본체를 식별합니다. 정지형 모드에서 상태·정지·비상정지와 명시적 래치 해제를 점검할 수 있습니다. 이동과 자세 명령은 정지로 처리합니다.

## 구현과 검증 범위

| 구성 | 현재 실행 경로와 상태 |
| --- | --- |
| 본체·안전 | 본체 MicroPython은 공식 MechDog API를 사용합니다. 명령 단절 600 ms 후 본체가 정지·래치합니다. 자동 재개 없이 사람이 상태를 확인합니다. A/B 동시 실물 watchdog 시험은 남았습니다. |
| 영상·낙상 | Windows Python의 `host/vision/`에 MJPEG 수신과 모델 작업자 인터페이스, 합성 증거 입력이 있습니다. 실제 추론 모델과 두 카메라 동시 수신·낙상 정확도는 검증 대기입니다. |
| 라이다 | Windows Python에서 USB 실물과 TCP 합성을 확인했습니다. J5 → Wi-Fi 실물 검증은 별도입니다. |
| SLAM·경로 | 같은 노트북의 WSL 2 Ubuntu 24.04에서 ROS 2 Jazzy와 `ros2/scan_node.py`를 실행하는 경로를 사용합니다. Windows 네이티브 Python에서 스캔·지도 변환을 시험했습니다. Ubuntu 배포판, ROS 노드 실행, 로봇망 TCP 도달, TF·odometry·SLAM·지도 연결·주행 실행기는 검증 대기입니다. [ROS 설치](https://docs.ros.org/en/jazzy/Installation/Ubuntu-Install-Debs.html) · [스캔 실행](../ros2/README.md) |
| 시나리오·대시보드 | 로컬 웹 정지형 모드와 A/B 합성 낙상·안내 모의 동작이 있습니다. 실제 영상·스캔·경로와 움직임을 한 프로세스에서 조립한 데모는 후속 구현입니다. |

[시연 시나리오](demo-scenario.md) · [영상 모델 계획](fall-detection-plan.md) · [LiDAR 통합](lidar-integration.md)
