# 메인 ESP32 Arduino 예비 판 — 컴파일 골격

현재 주 펌웨어는 순정 MicroPython + robot Python 코드입니다.
이 폴더는 **Python 판 실물 검증 후 이식할 설계·컴파일 골격**이며 장치에 굽는 펌웨어가 아닙니다.
Wi-Fi·라이다 수신·공식 MechDog 구동 백엔드가 없고 부팅 상태만 유지합니다.
이 골격을 올리면 순정 MicroPython이 사라지므로 배포/굽기 명령을 제공하지 않습니다.

## 컴파일

저장소 루트에서 `python tools/build_main_arduino.py`를 실행합니다.
ESP32 Arduino 코어 3.3.12, 컴파일용 FQBN `esp32:esp32:esp32`를 사용합니다.
이는 클래식 ESP32 대상으로 문법·링크를 확인하는 설정이며 실제 보드의 플래시·핀·파티션을 확인한 배포 설정이 아닙니다.
산출물은 `build/main_arduino/compile/`에만 둡니다. 합본·업로드 기능은 없습니다.
카메라 ESP32-S3 펌웨어와 빌드 폴더를 공유하지 않습니다.

## 이식 대응표

| Python 동작 | 제조사 Arduino 인터페이스에서 확인한 사실 | 이식 전 확인 |
| --- | --- | --- |
| move(step,angle) | move는 float 인자 2개를 받음 | speed_x/angle_rate와 Python 단위·범위가 같은지 미확인, 변환을 지어내지 않음 |
| action_run(name) | const char* 이름 인자 | 동작 파일·실행 시간과 허용 목록 |
| set_default_pose() | pose 포인터 선택 인자와 duration 기본 1000 | 완료 시점·대기·취소 가능성 |
| set_pose(xyz,abc,ms) | mech_pose_t와 duration | 구조체 좌표·회전 단위·축 대응 |
| homeostasis(bool) | bool 인자 | 실제 모드와 안전 정지 간 상호작용 |
| stop_action(), action_is_over() | 대조한 Arduino 클래스 선언에서 같은 이름을 찾지 못함 | **차단 항목**: 동작 중단·완료의 근거 있는 대응 없이는 구동 백엔드 활성화 금지 |
| Battery_power(), MPU.read_angle() | Python과 모듈 경계가 다름 | 제조사 Arduino 센서 API·반환 단위·실물 값을 대조 |

근거는 제조사 Arduino 인터페이스 선언입니다. 외부 코드를 복사하거나 자체 PWM·역기구학·서보 드라이버를 만들지 않습니다.
공식 API 대응을 찾지 못한 기능을 raw I2C/UART로 우회하지 않습니다.

## 동일하게 유지할 계약

- CMD/TEL·ROLE 규약, A/B 장치 ID와 별개인 주·보조 역할, 임대·세대·세션 확인.
- UDP 9100/9101, UART1 IO32/33·115200, TCP 20108 원시 중계.
- 600ms 명령 감시, ESTOP 우선·동작 중단+이동 정지, 저전압·예외·Wi-Fi 단절 래치.
- 사람 RESET과 이후 TEL 해제 확인. 역할 배정·재연결·재부팅만으로 이동하지 않음.
- 같은 가짜 장애 시나리오와 실제 정지 지연 확인을 통과하기 전 Python을 대체하지 않음.

추후 사용자가 전환할 때는 본체 전체 플래시와 main.py·설정을 먼저 백업하고,
문제 시 해당 보드 전체 플래시 백업 또는 순정 MicroPython과 저장한 Python 파일을 복구합니다.
현재는 그 전환 단계에 도달하지 않았습니다.
