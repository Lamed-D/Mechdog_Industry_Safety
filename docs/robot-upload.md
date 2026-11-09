# 메인 보드 Python 업로드와 복구

아래 장치 작업은 사용자만 실행합니다. 카메라 ESP32-S3에 이 파일을 올리지 않습니다.
로봇 A를 끝낸 뒤 B를 진행하고, 본체·카메라 COM 포트를 구분합니다.
주·보조 역할 통신을 쓰려면 두 로봇과 호스트를 같은 코드 세대로 갱신합니다.
A/B는 장치 식별자이고 역할은 [통신으로 배정](robot-redundancy.md)합니다. 구형 로봇은 ROLE를 거부하며 정지합니다.

1. 본체를 지지하고 다리 주변을 비웁니다. Python Editor로 연결하고 자동 실행을 중단합니다.
   기존 장치 `main.py`와 사용자 설정을 PC로 읽어 백업합니다. 백업은 저장소에 추가하지 않습니다.
2. PC에서 저장소 루트 기준 `python tools/bundle_robot.py --robot A`를 실행합니다.
   B는 `--robot B`입니다. 생성물은 `build/robot_A/main.py` 또는 `build/robot_B/main.py`입니다.
   로봇 ID만 생성 때 고정하며 Wi-Fi 값은 포함하지 않습니다.
3. `robot/secrets.example.py`를 참고해 사용자 `secrets.py`에 Wi-Fi 값을 작성합니다.
   이 파일은 커밋하거나 화면·로그로 공유하지 않습니다. 파일은 장치 최상위에 업로드합니다.
4. 백업을 확인한 뒤 해당 로봇의 생성 `main.py`를 Python Editor로 장치 최상위에 업로드합니다.
   실행 버튼이 자동 실행하는지 먼저 확인합니다. 기본은 boot 래치지만 MechDog 초기화 자체의 움직임은 실물 미검증입니다.
5. 첫 REPL 확인: 예외·MemoryError 유무, Wi-Fi 연결, Pi 텔레메트리의 ID·boot 래치·배터리·경고를 확인합니다.
   RESET·MOVE를 보내지 않습니다. 카메라 읽기는 observed/has_result=False가 기대값이며 낙상 인식은 unknown입니다.
6. 문제 시 자동 실행을 중단하고 저장한 기존 `main.py`와 설정을 되돌린 뒤 재시작합니다.
   REPL 접근이 안 되면 반복 재부팅하지 말고 제조사 복구 절차로 순정 MicroPython을 복원합니다.
   전체 플래시 복구가 필요하면 사용자가 보관한 해당 보드 백업을 사용합니다.

여러 파일 import의 편집기 전송 동작을 보장할 근거가 없어 단일 main 묶음을 제공합니다.
표준 `exec`와 모듈별 전역 사전을 사용하고 장치에서 파일을 만들지 않습니다.
두 ID의 생성물을 가짜 공식 모듈로 시작·ESTOP 시험했습니다. **순정 MicroPython의 실제 힙 여유와
exec 동작은 실물 확인 필요**입니다. 원본과 생성물이 함께 메모리에 놓이는 초기 순간이 있으므로 MemoryError면 중단·복구합니다.
여러 파일 방식은 robot의 py 파일과 custom_sensors/lidar_bridge.py를 장치 최상위에 두지만,
편집기에서 실제 import가 되는 것을 확인한 경우에만 사용합니다.

카메라 굽기·복구는 [별도 절차](vision-cam-firmware.md), 결과 기록은 [양식](user-tests/results-template.md)을 사용합니다.
