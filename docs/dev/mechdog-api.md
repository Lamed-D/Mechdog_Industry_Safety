# MechDog 제어 API 규칙

**관절·이동·자세·공식 센서·출력 등 로봇의 모든 제어는 Hiwonder 공식 MechDog Python API로만 합니다.**
예외는 두 가지입니다: **추가로 다는 비공식 센서 읽기**([6절](#6-추가-센서-비공식))와
**Pi 5와의 Wi-Fi 통신**([9절](#9-통신-로봇--pi-5)). 둘 다 로봇을 직접 움직이지 않습니다.

기준 문서: [MechDog Python Programming Projects (Hiwonder)](https://docs.hiwonder.com/projects/MechDog/en/latest/docs/4.Python_Programming_Projects.html)

## 0. 우리 로봇 구성

로봇은 **2대(로봇 A, 로봇 B)이며 둘 다 아래와 같은 구성**입니다. 역할은 [시연 시나리오](../demo-scenario.md) 참고.

| 부위 | 구성 | 제어 |
| --- | --- | --- |
| 다리 | **4개**(사족보행) | `move`, `transform`, `set_pose`, `set_default_pose`, `action_run`, `homeostasis` |
| 앞쪽 | **비전 모듈**(ESP32-S3 카메라) 장착 | `Hiwonder_IIC.ESP32S3Cam(iic)` |
| 팔·집게 | **없음** | — |
| 부가 서보(9·10번) | **연결된 장치 없음**(꼬리·적재함·발사대·뿔·날개도 없음) | `set_servo` 쓰지 않음 |
| 등 위 | **RPLIDAR A1M8-R6**(360° 2D 라이다, 최대 12 m) 테이프로 고정 | 비공식 센서, [6절](#6-추가-센서-비공식) |
| 추가 센서 | 그 밖의 비공식 센서 추가 예정 | [6절](#6-추가-센서-비공식) |

**처리 컴퓨터는 로봇에 싣지 않습니다.** Raspberry Pi 5 16GB를 **고정 위치**에 두고(부족하면 Jetson Orin Nano
Super), 지도 작성·자기 위치·경로 계획·쓰러진 사람 감지를 처리합니다. 로봇의 ESP32는 공식 API로 움직이기만 하고,
판단은 Pi 5가 내려서 Wi-Fi로 명령을 보냅니다([9절](#9-통신-로봇--pi-5)).

- 라이다는 테이프로 대충 고정하므로 **시연 전 매번 고정 상태와 방향(정면 기준 0°)** 을 확인합니다.
  흔들리거나 돌아가면 지도·위치가 틀어집니다.
- 라이다(약 170 g)를 실은 상태에서 걸음새·자세 값이 바뀔 수 있습니다. 실은 상태로 작은 값부터 다시 시험합니다.
- 없는 장치(팔, 집게, 꼬리 등)를 쓰는 코드를 작성하지 않습니다. 장치를 새로 달면 이 표를 먼저 고칩니다.
- 비전 모듈이 앞에 있으므로 `color_follow`, `line_follow`, `face_recognition` 결과는 **로봇 정면 기준**입니다.
- 비전 모듈은 5V 2A 이상 전원이 필요합니다. 추가 센서를 달 때 전원을 합산해 확인합니다.

## 1. 실행 환경

- 제어 보드: **ESP32(클래식)**, 순정 펌웨어 **MicroPython v1.21.0 (ESP-IDF v5.0.2)**. `machine.UART` 핀·버퍼 지정, `network.WLAN.PM_NONE` 지원.
- 업로드: Hiwonder Python Editor로 연결 후 다운로드. 로봇은 시작 시 장치의 `main.py`를 실행합니다.
- 펌웨어 방침: 메인 보드는 **MicroPython(이 문서의 공식 Python API)이 주 펌웨어**, Arduino 판은 Python 판 검증 후 옮겨 만드는 예비 펌웨어입니다.
  비전 모듈(ESP32-S3)은 Arduino로 개발합니다 → [펌웨어 방침](../firmware-strategy.md).
- 장치에 있는 기존 `main.py`를 덮어쓰거나 지우는 일, 펌웨어를 새로 굽는 일(ERASE 포함)은
  **사용자 확인 후에만** 합니다.

## 2. 반드시 지킬 것

1. **공식 모듈만 씁니다.** 제어 코드는 아래 모듈을 통해서만 하드웨어에 접근합니다.
   - `from HW_MechDog import MechDog`: 이동, 걸음새, 자세, 동작 그룹, 균형, 부가 서보
   - `import Hiwonder`: 버튼, 부저, 조도 센서, 도트 매트릭스, 백그라운드 스레드
   - `import Hiwonder_IIC`: I2C 장치(초음파, 음성 인식, MP3, ESP32-S3 카메라)
2. **로봇을 움직이는 직접 구동 코드를 만들지 않습니다.** `machine.PWM`·`machine.Pin`으로 다리·서보를
   직접 구동하거나, raw I2C·UART 바이트로 공식 장치를 직접 제어하거나, 자체 역기구학·서보 드라이버를
   새로 작성하지 않습니다. (추가 센서 **읽기**만 6절에 따라 예외)
3. **API에 없는 기능이 필요하면 멈추고 묻습니다.** 우회 구현하지 말고 이슈를 만들거나 사용자에게 확인합니다.
4. **문서에 없는 메서드·인자를 지어내지 않습니다.** 아래 표에 없는 호출을 쓰려면 문서에서 근거를 찾아
   PR에 링크합니다.
5. **값은 문서 범위 안에서만 씁니다.** 범위가 문서에 없으면 작은 값부터 시험하고 PR에 적습니다.

## 3. API 요약 (문서 기준)

`mechdog = MechDog()`

| 기능 | 호출 | 인자·범위 |
| --- | --- | --- |
| 이동 | `mechdog.move(step, angle)` | step: 보폭 mm, -100~100(음수=후진). angle: 회전 각도, -30~30(양수=왼쪽) |
| **정지** | `mechdog.move(0, 0)` | 전용 정지 함수 없음. 정지는 항상 이 호출 |
| 걸음새 | `mechdog.set_gait_params(lift_time, contact_time, lift_height)` | 발 들기 시간, 발 닿는 시간(ms로 추정), 발 들기 높이 mm. 범위 미기재 |
| 몸체 자세 | `mechdog.transform([x,y,z], [rx,ry,rz], time_ms)` | 이동 mm, 회전 도, 시간 ms. 범위 미기재 |
| 몸체 자세 | `mechdog.set_pose([x,y,z], [a,b,c], time)` | 인자 의미·단위 미기재. 예제 값만 사용 |
| 기본 자세 | `mechdog.set_default_pose()` | 네 다리로 서기 |
| 동작 그룹 | `mechdog.action_run("name")` | [4.1절](#41-동작-그룹-action_run) 16종. 끝날 때까지 기다리지 않으므로 뒤에 `time.sleep()` |
| 동작 그룹 끝남 확인 | `mechdog.action_is_over()` | 인자 없음. 끝났으면 참으로 보임(제조사 예제: `action_run` 뒤 짧게 기다린 다음 반복 확인). 공개 강좌에는 없음 |
| 동작 그룹 멈춤 | `mechdog.stop_action()` | 인자 없음. 실행 중인 동작 그룹을 멈춤(제조사 예제). 바로 멈추는지 실물 확인 전이므로 **항상 `move(0, 0)`과 함께** 부름 |
| 자기 균형 | `mechdog.homeostasis(True)` / `mechdog.read_homeostasis_status()` | 기울기 20° 넘으면 균형 모드 해제 |
| 부가 서보 | `mechdog.set_servo(servo_id, pulse, time_ms)` | 9·10번 부가 서보용. 다리 관절용이 아님. **우리 로봇은 연결된 장치가 없으므로 쓰지 않음** |

| 장치 | 생성 | 주요 호출 |
| --- | --- | --- |
| 초음파 | `Hiwonder_IIC.I2CSonar(Hiwonder_IIC.IIC(1))` | `getDistance()`(cm로 보임), `setRGB(n, r, g, b)` |
| 음성 인식 | `Hiwonder_IIC.asr_module(iic)` | `getResult()`(0=인식 없음), `speak(mode, id)` |
| MP3 | `Hiwonder_IIC.MP3(iic)` | `volume(v)`, `play(n)`, `pause()` |
| 비전 모듈(앞쪽, **장착**) | `Hiwonder_IIC.ESP32S3Cam(iic)` | `color_recognition()`, `color_follow(color)`, `line_follow(color)`, `face_recognition()` |
| 버튼 | `Hiwonder.Button(1)` | `Clicked(callback)` |
| 부저 | `Hiwonder.Buzzer()` | `playTone(freq, duration, wait)` |
| 조도 | `Hiwonder.LightSensor()` | `read()` |
| 도트 매트릭스 | `Hiwonder.Digitaltube()` | `setBrightness(n)`, `showNum(n)` |
| 스레드 | `Hiwonder.startMain(func)` | 백그라운드 함수 등록 |

**다리 관절은 개별 각도로 제어하지 않습니다.** 공식 API에 다리 관절 각도 호출이 없으므로, 다리는
`move`, `transform`, `set_pose`, `set_default_pose`, `action_run`, `homeostasis`로만 움직입니다.

## 4. 포즈·자세 목록

비전 모듈의 제조사 Python 얼굴 예제는 물리 **IIC 포트 1**을 코드의 `IIC(2)`에 연결하고
`ESP32S3Cam(iic).read_face()`를 호출합니다. 기존 배포 예제의 `face_recognition()`과 구분하여
장치에 `read_face`가 있으면 이를 우선합니다. 메서드 존재만으로 장치 응답을 확인했다고 보지 않습니다.
읽기 실패 시 임의 raw I2C로 우회하지 않으며 로봇 동작을 호출하지 않습니다.

### 4.1 동작 그룹 (`action_run`)

이름은 문서 철자 그대로 씁니다(`sit_dowm` 포함). 산업 현장에서 쓸 만한 것은 "용도" 열에 표시했습니다.

| 이름 | 동작 | 용도 |
| --- | --- | --- |
| `stand_four_legs` | 네 다리로 서기 | 기본·대기 |
| `normal_attitude` | 차렷 자세 | 기본·대기 |
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

문서 예제의 값입니다. 이 범위를 넘는 값은 작은 값부터 시험하고 PR에 적습니다.

| 자세 | 호출 | 문서 설명 |
| --- | --- | --- |
| 몸 높이기 20 mm | `mechdog.transform([0, 0, 20], [0, 0, 0], 1000)` | 1초 동안 20 mm 올림 |
| 몸 낮추기 30 mm | `mechdog.transform([0, 0, -30], [0, 0, 0], 1000)` | 1초 동안 30 mm 내림 |
| x축 회전 +15° | `mechdog.transform([0, 0, 0], [15, 0, 0], 500)` | 주석: Pitch / 본문: 왼쪽으로 기울기 |
| x축 회전 -30° | `mechdog.transform([0, 0, 0], [-30, 0, 0], 1000)` | 본문: 오른쪽으로 기울기 |
| y축 회전 +15° | `mechdog.transform([0, 0, 0], [0, 15, 0], 500)` | 주석: Roll / 본문: 앞으로 기울기 |
| y축 회전 -30° | `mechdog.transform([0, 0, 0], [0, -30, 0], 1000)` | 본문: 뒤로 기울기 |
| 앞으로 숙이기 | `mechdog.set_pose([0, 0, 0], [0, 20, 0], 300)` | 장애물을 밀기 전 숙인 자세 |
| 후진 준비 자세 | `mechdog.set_pose([-10, 0, -5], [0, 0, 0], 200)` | 후진 시작 전에 사용 |
| 자세 초기화 | `mechdog.set_pose([0, 0, 0], [0, 0, 0], 200)` | 후진 후 다른 동작 전에 사용 |
| 기본 서기 | `mechdog.set_default_pose()` | 네 다리로 서기 |

- **축 방향이 문서 안에서 엇갈립니다.** 코드 주석은 x=Pitch, y=Roll이고 본문은 x=좌우, y=앞뒤로 설명합니다.
  실제 로봇에서 방향을 확인하기 전에는 큰 각도를 쓰지 않습니다. 확인하면 이 표를 고칩니다.
- 걸으면서 자세를 바꿀 때는 걷기 속도를 줄이고 작은 값부터 씁니다.

### 4.3 걸음새 (`set_gait_params`)

| 설정 | 호출 | 문서 설명 |
| --- | --- | --- |
| 크고 느린 걸음 | `mechdog.set_gait_params(150, 500, 40)` | 발을 높이·천천히 듦 |
| 작고 빠른 걸음 | `mechdog.set_gait_params(100, 300, 20)` | 발을 낮게·빠르게 듦 |

### 4.4 부가 서보 (`set_servo`, 9·10번) — 사용 안 함

**우리 로봇에는 팔·집게·꼬리 등 부가 서보 장치가 없으므로 `set_servo`를 쓰지 않습니다.**
문서의 팔·집게·꼬리·적재함·발사대 예제도 가져오지 않습니다.
나중에 부가 장치를 달면 0절 표를 먼저 고치고, pulse 500~2500 범위 안에서만 씁니다
(문서 예제의 `set_servo(9, 450, 30)`은 범위 밖).

## 5. 문서에서 불확실한 점

실제로 확인하면 이 문서를 고치고 PR에 적습니다.

- `set_gait_params`의 시간 단위, `set_pose`의 리스트 의미와 시간 단위
- `action_is_over()`·`stop_action()`이 순정 펌웨어에 있는지, `stop_action()`이 동작 그룹을 바로 멈추는지(제조사 예제에만 있고 공개 강좌에 없음)
- `transform` 회전축 방향(4.2절)
- `homeostasis`를 끄는 Python 호출 없음(시리얼 프로토콜 `CMD|1|3|0|$`만 문서에 있음)
- IMU 원시값·배터리 전압을 읽는 Python 호출 없음(시리얼 `CMD|5|$`, `CMD|6|$`만 있음)
- 음성 모듈·초음파의 I2C 버스 번호가 문서 안에서 엇갈림

## 6. 추가 센서 (비공식)

이 프로젝트는 공식 모듈 외에 **센서를 추가로 답니다**(예: 가스, 온도, 불꽃 센서. 종류는 정해지는 대로 아래 표에 추가).
이 센서들은 공식 API가 없으므로 다음 규칙으로 직접 드라이버를 작성합니다.

### 6.1 허용 범위

- 추가 센서 **읽기**에 한해 MicroPython `machine` 모듈(`Pin`, `ADC`, `I2C`, `SoftI2C`, `UART`)을
  직접 써도 됩니다.
- 드라이버는 **`custom_sensors/` 폴더**에만 둡니다. 센서 하나에 파일 하나(`custom_sensors/<센서이름>.py`).
- 드라이버는 **값을 읽어서 돌려주기만** 합니다. 드라이버 안에서 `MechDog`를 만들거나 로봇을 움직이지 않습니다.
- 센서 값에 따른 동작(정지, 경고, 자세 변경)은 상위 코드에서 **공식 API**(`mechdog.move(0, 0)`,
  `Hiwonder.Buzzer` 등)로 합니다.
- 추가 센서용으로도 다리·부가 서보를 `machine.PWM`으로 구동하지 않습니다.

### 6.2 드라이버 작성 규칙

1. **실패하면 `None`을 돌려줍니다.** 연결 끊김·시간 초과·범위 밖 값을 0이나 "정상"으로 바꾸지 않습니다.
2. **읽기는 시간 제한이 있어야 합니다.** 센서 하나가 멈춰도 정지 로직이 막히지 않게 합니다.
3. **단위를 이름에 씁니다.** 예: `read_ppm()`, `read_celsius()`. 변환식·임계값의 근거(데이터시트)를 주석에 적습니다.
4. **공식 장치와 자원이 겹치지 않게 합니다.** 공식 모듈이 쓰는 핀·I2C 버스·주소를 피합니다.
   공식 I2C 버스를 같이 써야 하면 먼저 사용자에게 묻습니다.
5. **테스트는 가짜 `machine` 모듈로** PC에서 돌립니다(`tests/fakes/`). 실패·시간 초과 경우도 테스트합니다.

### 6.3 배선 기록

센서를 추가하면 이 표를 같은 PR에서 갱신합니다. 표에 없는 핀을 코드에서 쓰지 않습니다.

| 센서 | 모델 | 연결 방식 | 핀 / 버스 | I2C 주소 | 전원 | 드라이버 |
| --- | --- | --- | --- | --- | --- | --- |
| 라이다 | Slamtec RPLIDAR A1M8-R6 | UART(3.3V TTL, 115200bps) → 메인 ESP32 J5 → Wi-Fi(TCP) → Pi 5 | J5-4 IO32(RX), J5-3 IO33(TX), J5-2 GND ([lidar-integration.md](../lidar-integration.md) 4절) | — | 코어 5V 300~350mA(기동 최대 600mA) + 모터 5V 약 100mA, 1단계는 별도 5V | 중계: `custom_sensors/lidar_bridge.py`(원시 양방향, 로봇을 움직이지 않음), 처리: Pi 5 |

## 7. 안전 사용 규칙

- 반복문에서 움직일 때는 **센서 실패·예외·종료 경로에서 반드시 `mechdog.move(0, 0)`** 을 호출합니다
  (`try/finally`).
- 초음파·추가 센서 값이 없거나 비정상(`None`)이면 "위험 없음"으로 보지 말고 정지합니다.
- `action_run` 직후 바로 다른 동작을 보내지 않습니다. 동작 시간만큼 기다립니다.
- 비전 모듈은 5V 2A 이상 전원이 필요합니다(부족하면 영상이 깨짐). 추가 센서의 전원도 합산해 확인합니다.
- 앞쪽 비전 모듈이 바닥·장애물에 부딪히지 않게, 앞으로 숙이는 자세(`set_pose([0,0,0],[0,20,0],300)` 등)나
  몸 낮추기는 작은 값부터 씁니다.

## 8. 테스트 (PC에서)

- PC에는 `HW_MechDog`, `Hiwonder`, `Hiwonder_IIC`, `machine`이 없으므로, 테스트는 `tests/fakes/`의
  **가짜 모듈**로 같은 이름·같은 메서드를 흉내 내어 호출 기록을 검사합니다.
- 가짜 모듈에도 범위 검사(예: `move` step -100~100, `action_run` 이름 16종)를 넣어,
  범위 밖 값이나 없는 이름을 보내면 테스트가 실패하게 합니다.
- 부가 서보가 없으므로 가짜 `MechDog.set_servo`는 **호출되면 바로 실패**하게 합니다.

## 9. 통신 (로봇 ↔ Pi 5)

> **결정 대기 중.** 아래는 현재 정해진 원칙이고, 장비 구성(브리지 추가 여부, 전용 공유기)은 결정되면 고칩니다.

- **판단은 Pi 5, 동작은 로봇.** 로봇의 `main.py`는 Pi 5가 보낸 고수준 명령(이동·정지·동작 그룹)을 받아 공식 API로 실행합니다.
- **정지는 로봇이 스스로 합니다.** 명령이 일정 시간(예: 0.5초) 끊기면 Pi 5 지시를 기다리지 않고 `mechdog.move(0, 0)`.
  통신 지연·끊김이 있어도 로봇이 마지막 이동 명령을 계속 수행하지 않게 합니다.
- **Wi-Fi 통신 코드는 "통신 전용" 예외입니다.** MicroPython `network`·`socket`은 Pi 5와 메시지를 주고받는 데만 쓰고,
  하드웨어 제어는 여전히 공식 API로만 합니다. 이 예외도 2절처럼 별도 파일(예: `robot/comm.py`)에 모읍니다.
- 메시지는 짧은 텍스트로 하고, 로봇 ID(A/B)와 순번을 넣어 오래된 명령을 버릴 수 있게 합니다.

