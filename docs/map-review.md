# 지도 편집 검증

`host/map_review.py`는 [지도 작성 흐름](mapping-and-patrol.md)의 편집 안전 규칙을 검사하는 순수 함수입니다.
ROS·Supabase·이미지 모델을 실행하거나 로봇 이동을 허용하지 않습니다.

입력은 너비·높이·m/cell 해상도·원점 `(x, y, yaw)`·좌표계·행 우선 셀 배열입니다.
원점은 첫 셀의 왼쪽 아래입니다. `ros2.map_grid.from_occupancy_grid(message)`가 ROS 메시지의 Pose를 이 평면 표현으로 바꿉니다.
ROS 모듈을 가져오거나 노드를 시작하지 않는 읽기 함수이며, 실제 Jazzy 메시지 실행 확인은 남아 있습니다.
셀 수는 최대 1,000,000개이며 생성 시 복사해 원본 목록 수정에 영향을 받지 않습니다.
근거: [공식 격자 메시지](https://github.com/ros2/common_interfaces/blob/jazzy/nav_msgs/msg/OccupancyGrid.msg),
[공식 메타데이터](https://github.com/ros2/common_interfaces/blob/jazzy/nav_msgs/msg/MapMetaData.msg).

셀 값의 의미는 ROS에서도 응용별입니다. 여기서는 보수적으로 **0만 빈 공간**, -1은 미확인,
1..100은 모두 막힌 공간으로 정합니다. 확률 지도나 PGM을 불러올 때 이 의미로 변환하는 과정은 별도 검증이 필요합니다.

1. `review_edit(base, proposal)`은 크기·해상도·원점·좌표계가 다르면 거절합니다.
2. 미확인 → 빈 공간은 사람 승인 목록이 있어도 거절합니다. 새 관측으로 지도를 다시 만드는 절차가 필요합니다.
3. 장애물 → 빈 공간은 모든 셀의 행 우선 인덱스를 표시합니다. 장애물을 더하거나 미확인으로 막는 변경은 삭제 승인이 필요 없습니다.
4. `approve_edit`는 검토 당시 초안·제안의 SHA-256과 삭제 셀 전체의 승인 목록을 다시 대조합니다.
   하나라도 달라지면 재검토해야 합니다. 승인 인덱스를 `(x, y)`로 표시할 때는 `(index % width, index // width)`를 씁니다.

해시는 무결성 대조값이며 인증 수단이 아닙니다. 상위 계층에서 사람이 누구인지 확인하고 두 지도 해시·셀별 승인·시각·버전을
감사 기록으로 남겨야 합니다. 아직 원격 승인 API·지도 확정 저장소·경로 실행에는 연결하지 않았습니다.
이 검사 통과만으로 지도 밖 위험, 계단, 전원·시야·위치 추정·제동 여유가 검증되지는 않습니다.

## ROS 입력 제한

어댑터는 메시지와 같은 속성을 읽고 행 우선 signed 셀을 복사합니다. 배열·목록·튜플만 허용하며 길이가 지도 크기와 같아야 합니다.
좌표계·m/cell·x/y 원점을 유지하고 정규화된 쿼터니언을 yaw로 변환합니다.
평면 전용이므로 원점 z와 쿼터니언 x/y 성분의 절댓값 및 norm 제곱과 1의 차이에 1e-6 허용오차를 적용합니다.
이 범위를 벗어나면 3D 정보를 버리거나 자동 보정하지 않고 거절합니다. 허용오차는 형식 검사용이며 물리 기울기 보정값이 아닙니다.
미확인 -1은 그대로 유지하며, 변환 뒤에도 미확인→빈 칸 변경은 기존 검토 함수가 거절합니다.

근거: [ROS 지도 메타데이터](https://github.com/ros2/common_interfaces/blob/jazzy/nav_msgs/msg/MapMetaData.msg),
[쿼터니언 필드](https://github.com/ros2/common_interfaces/blob/jazzy/geometry_msgs/msg/Quaternion.msg),
[공식 회전 안내](https://github.com/ros2/ros2_documentation/blob/jazzy/source/Tutorials/Intermediate/Tf2/Quaternion-Fundamentals.rst).
TF·지도 신선도·확정 버전·권한·실제 ROS 구독/주행 연결은 이 함수에서 제공하지 않습니다.
전체 셀 복사·검사·해시는 10Hz 제어 잠금 밖에서 처리해야 합니다.
