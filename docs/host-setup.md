# Windows 노트북 호스트 실행 계획

개발·데모 자원은 운영자 2명, Windows 노트북 2대, MechDog 2대, A1M8 2대입니다. A와 B는 각자 노트북·로봇·라이다를 한 세트씩 맡습니다. 두 본체와 카메라를 공통 2.4 GHz 로봇망에 두고, 각 노트북은 자기 세트의 명령·상태, 영상, 라이다, 대시보드를 담당합니다.

| 운영자 | 노트북 | 본체·카메라 ID | LiDAR |
| --- | --- | --- | --- |
| A | Windows A, 로컬 콘솔 8090 | A | A 전용 USB 또는 본체 A의 TCP 20108 |
| B | Windows B, 로컬 콘솔 8090 | B | B 전용 USB 또는 본체 B의 TCP 20108 |

실물 본체마다 명령 송신 프로세스는 하나입니다. 두 노트북에서 같은 본체를 지정하거나, 조종 콘솔과 두 본체용 진단 어댑터를 동시에 연결하면 HELLO 세션이 충돌할 수 있습니다. 본체에 LiDAR TCP 연결도 한 개씩 사용합니다.

## 인터넷을 유지하는 로봇망

운영자 A의 노트북을 기존 인터넷 Wi‑Fi에 연결한 상태에서 Windows 11 모바일 핫스팟을 켭니다. A의 설정에서 공유 원본과 공유 방식은 Wi‑Fi, 대역은 2.4 GHz로 지정합니다. 운영자 B의 노트북, 두 본체와 두 카메라는 이 핫스팟에 접속합니다. A의 기존 인터넷 연결은 유지하고 B는 핫스팟을 통해 인터넷에 접속합니다. [Windows 모바일 핫스팟](https://support.microsoft.com/en-us/windows/experience/connectivity-networking/use-your-windows-device-as-a-mobile-hotspot)

- A에서 인터넷과 핫스팟 연결 장치 목록을 확인합니다. B에서 인터넷에 접속하고 담당 카메라 HTTP와 본체 TCP 20108을 확인합니다. 접속 장치끼리 통신이 막혀 B가 본체나 카메라에 도달하지 못하면, 두 운영자와 장치를 클라이언트 간 통신을 허용하는 공통 2.4 GHz 공유기에 연결합니다.
- 본체·카메라는 공유망에 접속할 수 있는 설정이어야 합니다. 기본 카메라 AP를 노트북의 인터넷 Wi‑Fi와 번갈아 선택하는 시험은 별도입니다. Windows가 두 SSID에 직접 동시 접속하는 기능은 어댑터와 드라이버에 의존합니다. [Microsoft Dual STA](https://learn.microsoft.com/en-us/windows-hardware/drivers/netcx/dual-sta-connectivity)
- 핫스팟 이름과 암호는 운영자가 로컬에서 관리합니다. 방화벽을 유지하고 콘솔 웹 포트는 각 노트북의 루프백에 둡니다. 시험 중 핫스팟이 꺼지거나 A가 절전으로 들어가면 두 팀의 링크 상태를 다시 확인하고 실물 임무를 재개하기 전에 정지를 점검합니다.

Windows 노트북 한 대에서 2.4 GHz 핫스팟을 켠 뒤 기존 인터넷 Wi‑Fi와 HTTPS 연결을 유지하는 것을 확인했습니다. 노트북 B 및 로봇·카메라의 핫스팟 참여와 장치 간 도달 여부는 실물 통합 시험에서 확인합니다.

## 개발 순서

1. [test_PC](../test_PC/README.md)에서 합성 시험을 먼저 실행합니다. 이어 A1M8을 노트북 USB에 연결해 장치 정보·상태·스캔·종료를 확인합니다.
2. 사용자 장비 시험에서 A/B 본체와 카메라에 서로 다른 주소를 배정합니다. 각 본체의 ID와 UDP 9100/9101, 카메라의 MJPEG 주소, 본체 LiDAR TCP 20108을 노트북에서 확인합니다. 개별 카메라 AP에서 성공한 시험과 공통 로봇망에서 두 대가 동시에 연결되는 시험을 구분합니다. 주소와 자격 정보는 로컬에 보관하고 로봇망 포트를 외부에 공개하지 않습니다.
3. 각 노트북의 [PC 조종 콘솔](../test_PC/robot_console/README.md)에서 담당 본체의 영상·상태·LiDAR와 정지를 확인합니다. 기존 단일 로봇 사용자 조작·카메라 시험은 [#105](https://github.com/Lamed-D/Mechdog_Industry_Safety/pull/105)에 기록돼 있습니다.
4. 각 노트북에서 담당 영상의 디코딩·추론 지연, 센서 신선도, SLAM 위치 오차를 측정합니다. 두 운영자가 동일한 버전의 확정 지도와 좌표계를 사용하고 관리자·사고 지점을 지정합니다.
5. 두 노트북은 사건 ID, 발견 로봇, 지도 좌표, 안내 상태를 주고받도록 통합합니다. 발견 쪽은 담당 로봇을 정지시키고, 안내 쪽만 자기 로봇의 경로를 계획해 움직입니다. 사건 전달과 지도 버전 검증, 사람 확인, 만료 및 안전 정지 검증이 끝난 뒤 자동 안내를 연결합니다. 클라우드 동기화는 후속 범위입니다.

## Windows CMD 실행 순서

1. 저장소 최상위에서 `test_PC\run.cmd all`을 실행합니다.
2. A의 CMD에서 `python -m test_PC.mock_station --robot A`, B의 CMD에서 `python -m test_PC.mock_station --robot B`를 실행합니다. 각 PC에서 자기 `http://127.0.0.1:8090`을 엽니다. 노트북 한 대에서 두 ID를 시험할 때는 순서대로 실행합니다.
3. `python -m tools.mock.demo_scenario --finder B --fault link`로 두 로봇의 합성 사건·역할 교환·링크 손실 흐름을 별도로 재현합니다.
4. 실물 시험 승인 후 각자 자기 카메라 URL과 본체 주소를 확인합니다. A는 `python -m test_PC.robot_console.server --robot A --robot-ip %ROBOT_A_IP% --allow-real --cam %CAM_A_URL% --relay-lidar`, B는 같은 명령의 ID와 환경 변수를 B로 바꿉니다. 로봇과 주소가 맞는지 잠긴 상태에서 확인합니다.

## 구현과 검증 범위

| 구성 | 현재 실행 경로와 상태 |
| --- | --- |
| 본체·안전 | 본체 MicroPython은 공식 MechDog API를 사용합니다. 명령 단절 600 ms 후 해당 본체가 정지·래치합니다. 자동 재개 없이 담당자가 상태를 확인합니다. 공동 임무 중 운영자 간 연결이 끊길 때의 양쪽 정지는 별도 통합 대상입니다. |
| 영상·낙상 | Windows Python의 `host/vision/`에 MJPEG 수신과 모델 작업자 인터페이스, 합성 증거 입력이 있습니다. 실제 추론 모델과 두 카메라 동시 수신·낙상 정확도는 검증 대기입니다. |
| 라이다 | Windows Python에서 USB 실물과 TCP 합성을 확인했습니다. J5 → Wi-Fi 실물 검증은 별도입니다. |
| SLAM·경로 | 각 노트북의 WSL 2 Ubuntu 24.04에서 ROS 2 Jazzy와 `ros2/scan_node.py`를 실행하는 경로입니다. 스캔·지도 변환을 Windows Python에서 시험했습니다. WSL·ROS 실행, 공통 지도 정합, SLAM·주행 연결은 검증 대기입니다. ROS 노드를 본체 중계에 연결할 때는 같은 LiDAR에 조종 콘솔 TCP를 동시에 연결하지 않습니다. [ROS 설치](https://docs.ros.org/en/jazzy/Installation/Ubuntu-Install-Debs.html) · [스캔 실행](../ros2/README.md) |
| 시나리오·대시보드 | A/B 각각의 로컬 조종·센서 화면과 중앙 합성 시나리오가 실행됩니다. 두 Windows 노트북 간 실시간 알림·임무 전달과 자율 안내 실행기는 후속 구현입니다. |

[시연 시나리오](demo-scenario.md) · [영상 모델 계획](fall-detection-plan.md) · [LiDAR 통합](lidar-integration.md)
