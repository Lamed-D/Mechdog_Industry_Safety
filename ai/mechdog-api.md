# MechDog 제어 API 규칙

**관절·이동·자세·공식 센서·출력 등 로봇의 모든 제어는 Hiwonder 공식 MechDog Python API로만 합니다.**
예외는 두 가지이며 둘 다 로봇을 직접 움직이지 않습니다.

1. 추가로 다는 **비공식 센서 읽기**([7절](#7-추가-센서-비공식))
2. 노트북과의 **Wi-Fi 통신**([9절](#9-통신-예외))

기준 문서: [MechDog Python Programming Projects (Hiwonder)](https://docs.hiwonder.com/projects/MechDog/en/latest/docs/4.Python_Programming_Projects.html).
근거 우선순위: **실물 REPL 결과 → 제조사 Python 예제 → 순정 펌웨어 문자열 → 공식 문서 설명**.
본체에 설치된 Python 구현 원본은 확보하지 못했으므로 예제·문자열 근거를 실제 구현 확인으로 간주하지 않습니다.
하드웨어 구성·핀·전원은 [hardware.md](hardware.md), 메인 보드 펌웨어(`firmware/robot/python/`, Arduino 이식)는 [firmware.md](firmware.md),
메시지 형식은 [protocol.md](protocol.md)를 봅니다.

## 0. 우리 로봇 구성 (요약)

현재 **MechDog 1대**. 나중에 같은 구성의 로봇 A/B 두 세트로 늘릴 수 있습니다(ID A/B는 확장용).

| 부위 | 구성 | 제어 |
| --- | --- | --- |
| 다리 | 4개(사족보행, 서보 8개) | `move`, `transform`, `set_pose`, `set_default_pose`, `action_run`, `homeostasis` |
| 앞쪽 | 비전 모듈(ESP32-S3) | `Hiwonder_IIC.ESP32S3Cam(iic)` |
| 팔·집게·꼬리 등 | **없음** | — |
| 부가 서보(9·10번) | **연결된 장치 없음** | `set_servo` 쓰지 않음 |
| 등 위 | RPLIDAR A1M8-R6, 테이프 고정 (**동결**: 대시보드 표시용만, [lidar-frozen.md](lidar-frozen.md)) | 비공식 센서, 7절 |

- 없는 장치를 쓰는 코드를 작성하지 않습니다. 장치를 새로 달면 [hardware.md](hardware.md)와 이 표를 먼저 고칩니다.
- 비전 모듈이 앞에 있으므로 `color_follow`, `line_follow`, 얼굴 결과는 **로봇 정면 기준**입니다.
- 라이다(약 170 g)를 실은 상태에서 걸음새·자세 값이 바뀔 수 있으므로 실은 상태로 작은 값부터 시험합니다.

## 1. 실행 환경

- 메인 보드: **ESP32(클래식)**, 순정 펌웨어 **MicroPython v1.21.0 (ESP-IDF v5.0.2)**, 소스 없는 바이너리. 다시 굽지 않고 `main.py`만 작성.
  `machine.UART` 핀·버퍼 지정, `network.WLAN.PM_NONE` 지원(문자열 확인).
- 업로드: Hiwonder Python Editor. 로봇은 시작 시 장치의 `main.py`를 실행합니다.
  모듈 파일을 순서대로 나눠 올립니다([firmware.md](firmware.md) 2절). 장치 메모리 여유는 REPL 확인 필요.
- 메인 보드 주 펌웨어는 MicroPython([`../firmware/robot/python/`](../firmware/robot/python/)), Arduino 판([`../firmware/robot/arduino/`](../firmware/robot/arduino/))은 예비 이식판입니다.
  비전 모듈(ESP32-S3)은 Arduino 맞춤 펌웨어입니다 → [firmware.md](firmware.md).
- 메인 보드의 기존 `main.py` 덮어쓰기·삭제, 펌웨어 굽기(ERASE 포함)는 **사용자만** 합니다(에이전트는 가이드 작성). 비전 모듈은 [rules.md](rules.md) 4.1절.

## 2. 반드시 지킬 것

1. **공식 모듈만 씁니다.**
   - `from HW_MechDog import MechDog`: 이동, 걸음새, 자세, 동작 그룹, 균형
   - `import Hiwonder`: 버튼, 부저, 조도 센서, 도트 매트릭스, 배터리, 백그라운드 스레드
   - `import Hiwonder_IIC`: I2C 장치(IMU, 초음파, 음성 인식, MP3, ESP32-S3 카메라)
2. **로봇을 움직이는 직접 구동 코드를 만들지 않습니다.** `machine.PWM`·`machine.Pin`으로 다리·서보 구동,
   raw I2C·UART 바이트로 공식 장치 제어, 자체 역기구학·서보 드라이버 작성 금지. (추가 센서 **읽기**만 7절 예외)
3. **API에 없는 기능이 필요하면 멈추고 묻습니다.** 우회 구현하지 않습니다.
4. **문서·이 표에 없는 메서드·인자를 지어내지 않습니다.** 쓰려면 근거를 찾아 PR에 적습니다.
5. **값은 문서 범위 안에서만 씁니다.** 범위가 없으면 작은 값부터 시험하고 PR에 적습니다.
   제조사 예제에 프로젝트 제한 밖 `move` 값이 있어도 제한(±100/±30)을 넓히지 않습니다.
6. 공식 장치를 raw I2C로 스캔·읽기·쓰기하는 판별 스크립트도 만들지 않습니다.

## 3. API 요약과 근거 대조

`mechdog = MechDog()`. "예제"=제조사 Python 예제, "문자열"=순정 펌웨어 이미지의 읽을 수 있는 문자열(역컴파일 안 함).
문자열 존재는 인자·반환값·실행 시간의 보증이 아닙니다.

### 3.1 MechDog

| 기능 | 호출 | 인자·범위 | 예제/문자열 | 우리 사용 |
| --- | --- | --- | --- | --- |
| 이동 | `move(step, angle)` | step 보폭 mm -100~100(음수=후진), angle 회전 -30~30(양수=왼쪽) | 있음/있음 | 이동 명령, 시작 정지 |
| **정지** | `move(0, 0)` | 전용 정지 함수 없음. 정지는 항상 이 호출 | 있음/있음 | 모든 정지·`finally` |
| 걸음새 | `set_gait_params(lift_time, contact_time, lift_height)` | 시간(ms로 추정), 높이 mm. 범위 미기재 | 있음/있음 | 런타임 미사용 |
| 몸체 자세 | `transform([x,y,z], [rx,ry,rz], time_ms)` | mm, 도, ms. 범위 미기재 | 있음/있음 | 런타임 미사용 |
| 몸체 자세 | `set_pose([x,y,z], [a,b,c], time)` | 의미·단위 미기재, 예제 값만 | 있음/있음 | 런타임 미사용 |
| 기본 자세 | `set_default_pose()` | 네 다리로 서기 | 있음/있음 | 동작 그룹 뒤 복귀 |
| 동작 그룹 | `action_run("name")` | 4.1절 16종. 끝날 때까지 기다리지 않음 → 뒤에 대기 | 있음/있음 | 허용 목록만 |
| 동작 끝 확인 | `action_is_over()` | 인자 없음. 끝났으면 참으로 보임(예제: 짧게 기다린 뒤 반복 확인). 공개 강좌에 없음 | 있음/있음 | 완료 확인 |
| 동작 멈춤 | `stop_action()` | 인자 없음. 즉시 멈추는지 실물 미확인 → **항상 `move(0, 0)`과 함께** | 있음/있음 | ESTOP·래치 정지 |
| 자기 균형 | `homeostasis(bool)`, `read_homeostasis_status()` | 기울기 20° 넘으면 균형 모드 해제. `homeostasis(False)`도 예제에 있음 | 있음/있음 | 런타임 미사용 |
| 부가 서보 | `set_servo(id, pulse, ms)` | 9·10번용, 다리용 아님 | 있음/있음 | **사용 금지** |

**다리 관절은 개별 각도로 제어하지 않습니다.** 공식 API에 다리 관절 각도 호출이 없습니다.

### 3.2 Hiwonder · Hiwonder_IIC

| 장치 | 생성 / 호출 | 근거·주의 | 우리 사용 |
| --- | --- | --- | --- |
| 스레드 | `Hiwonder.startMain(func)` | 예제·문자열 있음. 여러 루프 동시 실행 | 전역 조립 → 함수 → `startMain`, 매회 `sleep_ms` 양보 |
| 배터리 | `Hiwonder.Battery_power()` | 예제·문자열 있음. mV | 실패는 NA |
| 부저 | `Hiwonder.Buzzer()`, `playTone(freq, ms, wait)` | 있음 | 런타임 미사용 |
| 버튼 | `Hiwonder.Button(1/2)`, `Clicked(callback)` | 있음 | 런타임 미사용 |
| 조도 | `Hiwonder.LightSensor()`, `read()` | 문서 | J5(IO33)와 겹침 → 라이다와 함께 쓰지 않음([hardware.md](hardware.md)) |
| 도트 매트릭스 | `Hiwonder.Digitaltube()`, `setBrightness(n)`, `showNum(n)` | 문서 | — |
| 시리얼 | `Hiwonder.UART(9600)` | `CMD|...|$` 텍스트용 메서드만(`contains_data`, `read_uart_cmd`, `send_data`). 바이너리 읽기 없음 | 사용 안 함(J5는 라이다) |
| IMU | `Hiwonder_IIC.MPU()`, `read_angle()` | **실물(로봇 B)에서 `MPU()`는 인자 없음, `MPU(IIC(1))`은 TypeError.** 예제에는 `MPU(iic)` 형태도 있음 | 실패는 NA. 칩 종류·축 방향 실물 확인 필요 |
| 비전 모듈 | `Hiwonder_IIC.ESP32S3Cam(Hiwonder_IIC.IIC(2))`, `read_face()` | 예제·문자열 있음. 4.4절 | 얼굴 읽기 우선 |
| 비전(구형) | `face_recognition()`, `color_recognition()`, `color_follow(color)`, `line_follow(color)` | `face_recognition`은 예제에 있으나 **문자열에서 못 찾음** | 구형 장치 호환 읽기만, 없으면 unknown |
| 초음파 | `Hiwonder_IIC.I2CSonar(iic)`, `getDistance()`, `setRGB(n,r,g,b)` | 있음. 제조사 예제는 `IIC(1)`, `setRGB(0, r, g, b)`, `getDistance()`를 cm로 보고 ×10 해서 mm로 보냄. 단위 실물 확인 필요 | `firmware/robot/python/sonar.py`: 100 ms마다 거리 → TEL `sonar_mm`(표시용), 대시보드 `LED` 명령 → `setRGB`. IMU와 같은 `IIC(1)` 객체를 나눠 씀. 실물 미검증 |
| 음성 인식 | `Hiwonder_IIC.asr_module(iic)`, `getResult()`(0=없음), `speak(mode, id)` | 문서. 장착·버스 미확인 | — |
| MP3 | `Hiwonder_IIC.MP3(iic)`, `volume(v)`, `play(n)`, `pause()` | 문서. 장착·버스 미확인 | — |

## 4. 포즈·자세 목록

### 4.1 동작 그룹 (`action_run`)

이름은 문서 철자 그대로(`sit_dowm` 포함). `normal_attitude` 외 이름은 제조사 예제에서 확인했습니다.

| 이름 | 동작 | 용도 |
| --- | --- | --- |
| `stand_four_legs` | 네 다리로 서기 | 기본·대기 |
| `normal_attitude` | 차렷 자세 | 기본·대기. **예제 리터럴로 미확인 → 실물 확인 전 새 기능에 추가 금지** |
| `sit_dowm` | 앉기 | 정지·대기, 점검 |
| `go_prone` | 엎드리기 | 정지·대기, 이동 전 낮은 자세 |
| `nodding_motion` | 끄덕이기 | 확인 신호 |
| `scrape_a_bow` | 인사(절) | 사람 인식 시 신호 |
| `handshake` | 악수 | 시연 |
| `stretch_oneself` | 기지개 | 시연 |
| `rotation_pitch` | PITCH 방향 회전 | 시연·센서 스윕 |
| `rotation_roll` | ROLL 방향 회전 | 시연·센서 스윕 |
| `stand_two_legs` | 두 다리로 서기 | 시연 전용, **넘어질 위험** |
| `press_up` | 팔굽혀펴기 | 시연 전용 |
| `boxing` | 펀치 | 시연 전용 |
| `left_foot_kick` | 왼발 차기 | 시연 전용 |
| `right_foot_kick` | 오른발 차기 | 시연 전용 |
| `pee` | 오줌 싸기 자세 | 시연 전용 |

- "시연 전용"·"넘어질 위험" 동작은 현장 기능 코드에 쓰지 않습니다. 쓰려면 PR에 이유를 적습니다.
- 동작 그룹이 끝나면 `set_default_pose()`로 돌아온 뒤 다음 이동을 보냅니다.

### 4.2 몸체 자세 (`transform`, `set_pose`)

문서 예제 값입니다. 넘는 값은 작은 값부터 시험하고 PR에 적습니다.

| 자세 | 호출 | 문서 설명 |
| --- | --- | --- |
| 몸 높이기 20 mm | `transform([0, 0, 20], [0, 0, 0], 1000)` | 1초 동안 20 mm 올림 |
| 몸 낮추기 30 mm | `transform([0, 0, -30], [0, 0, 0], 1000)` | 1초 동안 30 mm 내림 |
| x축 회전 +15° | `transform([0, 0, 0], [15, 0, 0], 500)` | 주석: Pitch / 본문: 왼쪽으로 기울기 |
| x축 회전 -30° | `transform([0, 0, 0], [-30, 0, 0], 1000)` | 본문: 오른쪽으로 기울기 |
| y축 회전 +15° | `transform([0, 0, 0], [0, 15, 0], 500)` | 주석: Roll / 본문: 앞으로 기울기 |
| y축 회전 -30° | `transform([0, 0, 0], [0, -30, 0], 1000)` | 본문: 뒤로 기울기 |
| 앞으로 숙이기 | `set_pose([0, 0, 0], [0, 20, 0], 300)` | 장애물을 밀기 전 숙인 자세 |
| 후진 준비 자세 | `set_pose([-10, 0, -5], [0, 0, 0], 200)` | 후진 시작 전 |
| 자세 초기화 | `set_pose([0, 0, 0], [0, 0, 0], 200)` | 후진 후 다른 동작 전 |
| 기본 서기 | `set_default_pose()` | 네 다리로 서기 |

- **축 방향이 문서 안에서 엇갈립니다**(주석 x=Pitch·y=Roll, 본문 x=좌우·y=앞뒤). 실물 확인 전에는 큰 각도를 쓰지 않습니다.
- 걸으면서 자세를 바꿀 때는 걷기 속도를 줄이고 작은 값부터 씁니다.
- 앞쪽 비전 모듈이 바닥에 부딪히지 않게 숙이기·낮추기는 작은 값부터 씁니다.

### 4.3 걸음새 (`set_gait_params`)

| 설정 | 호출 | 문서 설명 |
| --- | --- | --- |
| 크고 느린 걸음 | `set_gait_params(150, 500, 40)` | 발을 높이·천천히 듦 |
| 작고 빠른 걸음 | `set_gait_params(100, 300, 20)` | 발을 낮게·빠르게 듦 |

### 4.4 비전 모듈 읽기

- 제조사 최신 얼굴 예제: **물리 IIC 포트 1 → 코드 `IIC(2)`**, `ESP32S3Cam(iic).read_face()`. 다른 강좌에는 카메라 `IIC(1)`도 있으므로
  물리 포트 번호와 코드 IIC 번호를 숫자만으로 일괄 대응하지 않습니다.
- 장치에 `read_face`가 있으면 우선하고, 없을 때만 `face_recognition()`을 씁니다. 메서드 존재 ≠ 장치 응답 확인.
- 읽기 실패 시 raw I2C로 우회하지 않고 로봇 동작도 호출하지 않습니다.
- 카메라 안 인식 대신 맞춤 영상 펌웨어를 쓰므로 I2C "결과 없음"은 정상 연결 상태일 수 있으며, **사람이 없다는 증거로 쓰지 않습니다.**

### 4.5 부가 서보 (`set_servo`, 9·10번) — 사용 안 함

부가 장치가 없으므로 `set_servo`를 쓰지 않고 문서의 팔·집게·꼬리·적재함·발사대 예제도 가져오지 않습니다.
나중에 부가 장치를 달면 0절 표를 먼저 고치고 pulse 500~2500 안에서만 씁니다(문서 예제 `set_servo(9, 450, 30)`은 범위 밖).

## 5. 불확실한 점과 사용 금지 후보

**문자열에서만 확인한 후보 — 실물 REPL 확인 전 사용 금지, 인자·단위 추측 금지:**
`run_status`, `wait_action_over`, `read_servo`, `read_all_servo`, `read_offset`, `set_offset`, `save_offset`, `set_angleoffset`.
보정 저장·서보 쓰기는 존재 확인만 하고 호출하지 않습니다.

실물로 확인해야 할 것(확인하면 이 문서를 고치고 PR에 적음):

- `set_gait_params` 시간 단위, `set_pose` 리스트 의미·시간 단위
- `stop_action()`이 동작 그룹을 즉시 멈추는지, `action_is_over()` 반환 형태
- `transform` 회전축 방향(4.2절)
- IMU 실제 칩: 순정 문자열에 MPU6050·QMI8658 이름이 모두 있음. `MPU` 클래스 이름·`read_angle` 성공은 칩 종류를 증명하지 않음
  → 보드 실크·칩 마킹·회로도 버전과 공식 읽기 결과를 함께 기록
- 음성 모듈·초음파의 I2C 버스 번호(문서 안에서 엇갈림), `getDistance` 단위
- `homeostasis` 끄기: 예제의 `homeostasis(False)`가 있으나 실물 효과 미확인
- 공식 Python 호출의 블로킹 시간·`startMain` 스케줄링

## 6. 제조사 인터페이스 (참고용, 우리 제어 경로 아님)

### 6.1 I2C 장치 주소

주소가 있다고 해서 장치가 장착됐거나 그 버스에서 응답한다고 보지 않습니다. 제어는 `Hiwonder_IIC`로만 합니다.

| 장치 | 주소 | 근거·상태 |
| --- | --- | --- |
| MPU6050 | 0x68 | 제조사 라이브러리. 실제 칩 확인 필요 |
| QMI8658 | [확인 필요] | 순정 문자열에 이름만. 판별 전 raw 접근 금지 |
| 초음파 | 0x77 | 제조사 라이브러리. 장착 여부 별도 확인 |
| 카메라 구형 레지스터 방식 | 0x53 | 맞춤 펌웨어 기본 주소. Python 세대별 응답 확인 필요 |
| 카메라 명령 방식 | 0x52 | 제조사 카메라 예제. 0x53과 동시에 응답하지 않음 |
| 음성 | 0x79 | 제조사 라이브러리. 장착·버스 미확인 |
| MP3 | 0x7B | 제조사 라이브러리. 장착·버스 미확인 |
| 별도 IoT Wi-Fi 모듈 | 0x69 | [공식 IoT 강좌](https://wiki.hiwonder.com/projects/MechDog/en/latest/docs/9.IOT_Expanded_Lesson.html). 우리는 메인 ESP32 내장 Wi-Fi를 쓰며 이 모듈을 전제하지 않음 |

I2C 신호 핀·카메라 슬레이브 핀은 [hardware.md](hardware.md).

### 6.2 제조사 시리얼·앱 기능 코드

제조사 시리얼 예제는 J5에서 9600bps 8N1, `CMD|...|$` 메시지를 씁니다([공식 시리얼 강좌](https://docs.hiwonder.com/projects/MechDog/en/latest/docs/5.Arduino_Programming_Projects.html)).
우리 라이다 UART(115200bps)와 포트가 같으므로 **이 예제 프로그램은 업로드하지 않습니다.**

| 기능 코드 | 의미 | 단위·주의 |
| --- | --- | --- |
| 1 | 자세·자기 균형 (`CMD|1|3|0|$` = 균형 끄기) | 하위 기능별 인자, 좌표 축 문서 세대 차이 |
| 2 | 기본·사용자 동작 그룹 | 번호 ↔ 동작 이름 대응 확인 필요 |
| 3 | 방향별 이동 | 우리 `move(step, angle)`과 다른 인터페이스 |
| 4 | 초음파 읽기·회피 | 반환 mm |
| 5 | IMU 기울기 | x/y 각도(도) |
| 6 | 배터리 | mV |

- 제조사 앱·군집 메시지를 우리 UDP 제어로 그대로 전달하지 않습니다.
- 제조사 Wi-Fi 예제는 `STA_IF` + UDP 9027을 씁니다(모든 앱 세대 공통이라 단정하지 않음).
- 우리 포트: CMD 9100 / TEL·ACK 9101 / 라이다 TCP 20108 / 카메라 HTTP 80·스트림 81 → [protocol.md](protocol.md).

### 6.3 동작 편집기·보정

- 공식 PC 편집기([동작 편집 안내](https://docs.hiwonder.com/projects/MechDog/en/latest/docs/7.Action_Editing_Course.html))는 동작별 시간·서보 값 목록을 편집하고,
  좌표 모드는 다리 x/z 위치를 조절합니다(제시 범위 X -40~140, Z -120~-50, 보정 편차 -100~100).
  이 값들은 원점·단위 설명이 문서 안에서 불일치하므로 **지도 좌표, `move` 인자, 공식 Python 자세·후보 API 인자 범위로 쓰지 않습니다.**
- 공개 동작 파일 표본(`.rob`, JSON): 최상위 `Actions` 목록, 항목마다 정수 `Duration`·정수 목록 `Servos`(관측 8개). 표본 한 건이라 스키마·단위 보증 없음.
  변환기·업로더·직접 서보 제어는 만들지 않습니다.
- 사용자 동작 슬롯 번호는 편집기에서 내려받을 때 고른 번호이며 앱의 사용자 이름과 별개입니다.
- 보정 기준은 제조사 출하 상태. 편집기 연결 자체가 자세를 바꿀 수 있으므로 **사용자 실물 작업으로만** 합니다.

## 7. 추가 센서 (비공식)

### 7.1 허용 범위

- 추가 센서 **읽기**에 한해 MicroPython `machine`(`Pin`, `ADC`, `I2C`, `SoftI2C`, `UART`)을 직접 써도 됩니다.
- 드라이버는 [`../firmware/robot/python/`](../firmware/robot/python/)에 센서 하나당 파일 하나(`<센서이름>.py`, 예: `lidar_bridge.py`)로 두고 다른 모듈과 섞지 않습니다.
- 드라이버는 **값을 읽어서 돌려주기만** 합니다. 안에서 `MechDog`를 만들거나 로봇을 움직이지 않습니다.
- 센서 값에 따른 동작(정지·경고·자세)은 상위 코드에서 공식 API로 합니다.
- 추가 센서용으로도 다리·부가 서보를 `machine.PWM`으로 구동하지 않습니다.

### 7.2 드라이버 작성 규칙

1. **실패하면 `None`.** 연결 끊김·시간 초과·범위 밖 값을 0이나 "정상"으로 바꾸지 않습니다.
2. **읽기에 시간 제한.** 센서 하나가 멈춰도 정지 로직이 막히지 않게 합니다.
3. **단위를 이름에**(`read_ppm()`, `read_celsius()`). 변환식·임계값 근거(데이터시트)를 주석에 적습니다.
4. **공식 장치와 자원 겹침 금지.** 공식 모듈의 핀·I2C 버스·주소를 피합니다. 공식 I2C 버스를 같이 써야 하면 먼저 사용자에게 묻습니다.
5. **실패·시간 초과 경로를 실물에서 확인**합니다(센서 분리·전원 차단 시 `None`과 정지 로직 유지). 확인 전에는 PR에 실물 미검증으로 적습니다.

### 7.3 배선 기록

센서를 추가하면 같은 PR에서 이 표와 [hardware.md](hardware.md)를 갱신합니다. 표에 없는 핀을 코드에서 쓰지 않습니다.

| 센서 | 모델 | 연결 | 핀 / 버스 | 전원 | 드라이버 |
| --- | --- | --- | --- | --- | --- |
| 라이다(동결) | RPLIDAR A1M8-R6 | UART1 3.3V TTL 115200bps → 메인 ESP32 J5 → Wi-Fi TCP 20108 → 노트북 | J5-4 IO32(RX), J5-3 IO33(TX), J5-2 GND | 별도 5V(1단계) | [`../firmware/robot/python/lidar_bridge.py`](../firmware/robot/python/lidar_bridge.py) 원시 양방향 중계 |

라이다 UART 설정 `machine.UART(1, baudrate=115200, rx=32, tx=33, rxbuf=4096)`: 순정 이미지에 UART·rxbuf 문자열은 있으나 숫자 인자 동작은 J5 루프백으로 확인해야 합니다.

## 8. 안전 사용 규칙

- 반복문에서 움직일 때는 **센서 실패·예외·종료 경로에서 반드시 `move(0, 0)`**(`try/finally`). 예외·종료는 `stop_action()`과 `move(0, 0)`을 함께 시도합니다.
- 초음파·추가 센서 값이 없거나 비정상(`None`)이면 "위험 없음"으로 보지 않고 정지합니다.
- `action_run` 직후 다른 동작을 보내지 않습니다. 동작 시간만큼 기다리거나 `action_is_over()`로 확인합니다.
- 비전 모듈은 5V 2A 이상 전원 필요(부족하면 영상 깨짐). 추가 센서 전원도 합산해 확인합니다.
- 로봇 본체 업로드·구동은 사용자만(비전 모듈 굽기는 [rules.md](rules.md) 4.1절).

## 9. 통신 예외

- **판단은 노트북, 동작은 로봇.** `main.py`는 노트북의 고수준 명령(이동·정지·동작 그룹)을 받아 공식 API로 실행합니다.
- **정지는 로봇이 스스로.** 명령이 **600 ms** 끊기면 노트북 지시 없이 `move(0, 0)` 후 래치. 마지막 이동 명령을 계속 수행하지 않습니다.
- MicroPython `network`·`socket`은 노트북과 메시지를 주고받는 데만 쓰고, 별도 파일([`../firmware/robot/python/comm.py`](../firmware/robot/python/comm.py))에 모읍니다.
  하드웨어 제어는 여전히 공식 API로만 합니다.
- 메시지는 짧은 텍스트, 로봇 ID와 순번을 넣어 오래된 명령을 버립니다. 형식은 [protocol.md](protocol.md).

## 10. 확인 방법

- PC에는 공식 모듈(`HW_MechDog`, `Hiwonder`, `Hiwonder_IIC`)이 없으므로 동작 확인은 **실물에서만** 합니다. 본체 업로드·구동은 사용자만 하며 절차는 [robot-tests.md](robot-tests.md).
- 실물로 확인하지 못한 동작·값은 문서와 PR에 "실물 미검증"으로 남깁니다.
