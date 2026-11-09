# Pi 도착 후 /scan 실행

Pi·ROS 실기는 미검증입니다. 지금은 PC 합성 테스트만 실행합니다. ROS는 핵심 로직과 별개인 선택 의존성입니다.
Jazzy 환경은 [호스트 설치](../docs/host-setup.md)를 따르고 `ros-jazzy-sensor-msgs`가 설치됐는지 확인합니다.

저장소 최상위에서 각 명령을 별도 터미널에 실행합니다. 아래 기본값은 루프백 합성 서버입니다.

```bash
python -m tools.mock.mock_lidar --port 20108
python -m tools.mock.mock_lidar --port 20109
source /opt/ros/jazzy/setup.bash
export ROS_DOMAIN_ID=42 ROS_LOCALHOST_ONLY=1
python -m ros2.scan_node --robot A --host 127.0.0.1 --port 20108
python -m ros2.scan_node --robot B --host 127.0.0.1 --port 20109
ros2 topic hz /robot_a/scan
ros2 topic echo /robot_b/scan --once
```

환경 설정은 ROS를 쓰는 모든 터미널에 동일하게 적용합니다. 실물 주소로 바꾸는 것은 연결 시험 승인을 받은 뒤입니다.
노드 종료는 Ctrl+C이며 종료 시 라이다 STOP을 시도합니다. 로봇 이동 명령은 보내지 않습니다.

각도는 정면 0·반시계 양수인 ROS 기준으로 변환하며 기본 direction=-1입니다. 실제 장착 방향과 정면은
수령 후 확인하여 `--direction`과 `--offset-deg`로 교정합니다. TF·odometry·SLAM은 이 노드가 생성하지 않습니다.
거리 0·품질 0·범위 밖·빈 각도는 NaN으로 남깁니다. 빈 각도를 안전한 빈 공간으로 해석하면 안 됩니다.
재연결 때 부분 회전을 버리고 최대 2개 프레임만 보관하며 300ms 넘게 대기한 프레임은 버립니다.
하드웨어 타임스탬프가 없어 첫 빔 시각은 수신 시각 기반 추정입니다. 네트워크 지연·보행 왜곡은 보정하지 않습니다.
재배열한 각도 bin에 균일한 취득 시간을 주장하지 않도록 time_increment=0으로 둡니다.
건강 Warning/오류 코드를 로그로 노출하고 Error는 재시도를 중단합니다. 자동 RESET은 하지 않습니다.

공개 메시지 정의: [LaserScan](https://github.com/ros2/common_interfaces/blob/jazzy/sensor_msgs/msg/LaserScan.msg).

지도 입력의 순수 변환은 `ros2.map_grid.from_occupancy_grid`를 사용합니다.
평면 Pose·정규화 회전·셀 배열을 검사해 [지도 편집 안전 검사](../docs/map-review.md)의 Grid로 변환합니다.
구독·지도 확정·이동은 실행하지 않으며 실제 ROS 메시지 연동은 Pi에서 확인해야 합니다.
합성 프레임 변환은 검증했지만 Pi의 ROS 실행·QoS·실제 센서 방향·두 대 부하는 사용자 확인 항목입니다.
