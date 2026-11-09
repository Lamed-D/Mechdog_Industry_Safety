# MechDog + RPLIDAR A1M8-R6 + Raspberry Pi 5 연동 설계

## 중계 진단 지표

`LidarBridge.metrics()`는 UART 관측 수위·최대 수위, 미송신 바이트·나이, 양방향 총 바이트,
연결 전 버린 바이트, TCP 송신 정체 횟수와 최근 표본 구간의 bytes/s를 제공합니다.
실행 중인 앱을 REPL에서 확인할 때 읽기용으로 사용할 수 있으며 새 UART·소켓을 열지 않습니다.
처리량은 주입된 ticks 시계로 1초 이상 구간에서 계산하고 표본 전/접속 종료 뒤에는 None입니다.
이는 소프트웨어 처리량이며 UART 하드웨어에서 잃은 바이트를 계수하는 기능은 아닙니다.
`drained`는 연결 전 의도적으로 버린 바이트이고 실제 오버런 손실과 구분합니다.

UART 수위가 설정 버퍼의 75% 이상이거나 TCP 미송신 묶음이 100ms 이상이면 TEL에 `lidar_backlog`를 보냅니다.
두 임계는 실측 전 가정이며 전송 지연을 드러내기 위한 것입니다. 호스트는 경고 중 새 MOVE를 막습니다.
메인 보드의 기존 래치 동작과 원시 바이트 순서는 유지합니다. 경고는 주기적으로 갱신되고 해소 시 사라집니다.
TEL 길이 제한에 따라 덜 급한 경고가 생략될 수 있으므로 호스트의 스캔 신선도 검사도 유지합니다.
호스트와 A/B를 함께 갱신해야 새 경고 낱말을 해석할 수 있습니다.

기준 자료: 제조사(Hiwonder·Slamtec)가 제공한 회로도·사양서·예제·데이터시트 (저장소에는 올리지 않음)
표기: **[확인]** 개발 자료·데이터시트에서 확인함 / **[추정]** 근거는 있으나 직접 확인 못 함 / **[확인 필요]** 실물·추가 자료로 확인해야 함

---

## 1. 구현 가능 여부: **조건부 가능**

별도 ESP32 보드 없이 **MechDog 메인 컨트롤러의 GPIO 포트(J5: IO32·IO33)를 UART로 써서** 라이다를 받고,
메인 컨트롤러의 Wi-Fi로 Pi 5에 보낼 수 있습니다. 조건은 아래 세 가지입니다.

1. **라이다 전원은 별도 5V로 시작**합니다. MechDog 5V 레일의 여유 전류가 자료에 없습니다(7절).
2. **라이다 모터는 CTRL_MOTO를 5V에 묶어 항상 켜기**로 합니다. J5의 두 핀을 UART에 다 쓰므로 모터 제어용 GPIO가 남지 않습니다.
3. **걸음이 흔들리지 않는지 실측**합니다. 걸음 제어는 C 타이머에서 돌아가는 것으로 보여 영향이 작을 것으로 예상하지만,
   MicroPython 펌웨어는 소스가 없어 확인이 필요합니다(2.6절).

## 2. 개발 자료에서 확인한 근거

### 2.1 메인 컨트롤러 칩은 ESP32-S3가 아니라 **ESP32(클래식)** 입니다 [확인]

| 근거 | 내용 |
| --- | --- |
| 제조사 회로도 (V1.2) | 메인 모듈이 **ESP32-DevKitC**(IO34~IO39, SD0~SD3 핀이 있는 클래식 ESP32 배치) |
| 제조사 기술 사양서 1절 | "ESP32-S dual-mode SoC chip"(S3 아님) |
| 같은 문서 3절 | **ESP32-S3는 비전 모듈**의 칩 |

제품 홍보 이미지의 "ESP32-S3"는 비전 모듈과 섞인 표기로 보입니다. 아래 설계는 클래식 ESP32 기준입니다.
보드 실크의 회로도 버전(V1.0/V1.2)은 **[확인 필요]** 입니다.

### 2.2 GPIO 포트 J5 핀 배치 [확인]

제조사 회로도 (V1.2) "GPIO Expansion Circuit":

| J5 핀 | 신호 |
| --- | --- |
| 1 | 5V |
| 2 | GND |
| 3 | **IO33** |
| 4 | **IO32** |

커넥터 실물에서 1번 핀 위치(보드 실크의 표시)는 **[확인 필요]** 입니다. 같은 회로도에서 I2C 포트는 5264 계열 4핀으로 표기되어 있고,
J5의 커넥터 형번은 회로도에 적혀 있지 않습니다 **[확인 필요]**.

### 2.3 J5를 UART로 쓰는 공식 예제가 있습니다 [확인]

- 제조사 Python 시리얼 통신 강좌 (마스터-슬레이브 통신 원리) 하드웨어 연결 절:
  USB 어댑터의 **TXD·RXD·GND를 MechDog의 IO32·IO33·GND에** 연결, TX/RX는 교차. 기본 9600bps 8N1.
  → **IO32 = MechDog RX, IO33 = MechDog TX** 입니다 **[확인]**. 제조사 Arduino 시리얼 예제가 `HardwareSerial(1)`을
    `rxPin 32`, `txPin 33`으로 열어 같은 방향을 씁니다(첫 실물 연결에서 응답으로 다시 확인).
- 제조사 Python 예제의 `Hiwonder.UART(9600)`은 이 포트를 UART로 엽니다.
  다만 `Hiwonder.UART`는 `CMD|...|$` 텍스트 명령용 메서드(`contains_data`, `read_uart_cmd`, `send_data`)만 보이고,
  라이다의 바이너리 데이터를 그대로 읽는 메서드는 자료에 없습니다 → 라이다에는 MicroPython `machine.UART`를 씁니다.

### 2.4 다른 기능과의 핀 충돌 [확인]

제조사 회로도 (V1.2)(ESP32-DevKitC Module Circuit)와 제조사 Arduino 라이브러리의 서보 핀 목록를 맞춰 본 결과:

| 기능 | 핀 |
| --- | --- |
| 서보 1~10 | IO25, 26, 27, 14, 16, 17, 15, 2, 0, 4 |
| 서보 11(회로도에만) | IO12 |
| I2C 1 (SDA1/SCL1) | IO22 / IO23 |
| I2C 2 (SDA2/SCL2) | IO19 / IO13 |
| 부저 / LED / 버튼 | IO21 / IO18 / IO5 |
| 배터리 전압 / IMU 인터럽트 | IO34 / IO35 |
| USB 시리얼(REPL, UART0) | IO1 / IO3 |
| **GPIO 포트 J5** | **IO32 / IO33 — 다른 기능과 겹치지 않음** |

주의: 제조사 Arduino 라이브러리는 터치 센서를 IO33(`Touch_Pin 33`), 조도 센서를 `analogRead(33)`으로 읽습니다.
**우리는 J5에 라이다를 꽂으므로 터치·조도 센서를 J5에 같이 쓰지 않습니다.**

### 2.5 추가 하드웨어 UART를 쓸 수 있는가 [확인]

- 클래식 ESP32에는 UART0·1·2가 있고, 핀을 자유롭게 지정할 수 있습니다(ESP32 GPIO matrix).
- UART0는 USB REPL(IO1/IO3)이 씁니다. 회로도에 "IO17/TX2, IO16/RX2"로 적힌 UART2 기본 핀은 **서보 5·6**이 씁니다.
- 따라서 **UART1을 IO32(RX)·IO33(TX)에 지정**해서 씁니다: `machine.UART(1, baudrate=115200, rx=32, tx=33, rxbuf=4096)`.
- 순정 펌웨어(MicroPython v1.21.0)의 `machine.UART`는 `baudrate`, `tx`, `rx`, `txbuf`, `rxbuf`, `timeout`, `timeout_char` 인자를
  지원합니다 **[확인: 순정 펌웨어 바이너리의 UART 표현 문자열]**. 실제 동작은 J5 루프백 시험으로 확인합니다.

### 2.6 펌웨어 유지·Wi-Fi·Python 제어와 충돌하는가

| 항목 | 판단 | 근거 |
| --- | --- | --- |
| 기존 펌웨어 유지 | **가능** — 펌웨어를 다시 굽지 않고 `main.py`만 작성 | 순정 펌웨어는 **MicroPython v1.21.0 (ESP-IDF v5.0.2, 2026-03-06 빌드)** 소스 없는 바이너리 [확인]. 수정 대상 아님 |
| Wi-Fi | **가능** [확인] | 제조사 군집 제어 예제 `main.py`: `network.WLAN(network.STA_IF)`, `socket`(UDP), `machine.unique_id()`를 메인 보드에서 사용 |
| 동시 실행(스레드) | **가능** [확인] | 군집 제어 예제와 시리얼 통신 예제가 `Hiwonder.startMain(func)`로 여러 루프를 동시에 돌림 |
| 걸음 제어와 충돌 | **영향 작을 것으로 예상** | 순정 펌웨어에 C로 만든 MechDog 모듈과 `pwm_servo_update_timer`가 들어 있음 [확인] → 서보 출력은 Python과 별개인 C 타이머가 갱신. UART 수신도 ESP-IDF 드라이버가 인터럽트로 `rxbuf`에 쌓음. 걸음 궤적 계산이 C인지 Python 래퍼인지는 **[확인 필요]** → 보행 중 중계 실측(10절 10단계) |
| Wi-Fi 절전 끄기(`pm=PM_NONE`) | **지원** [확인] | 순정 펌웨어에 `PM_NONE`, `PM_PERFORMANCE` 상수가 있음. 실제 지연 개선은 실측 |

덤으로 확인한 것: 공식 예제에서 `mechdog.homeostasis(False)`(균형 끄기), `Hiwonder_IIC.MPU(i2c1).read_angle()`(기울기),
`Hiwonder.Battery_power()`(배터리)가 Python API로 쓰입니다(제조사 시리얼 통신 예제). mechdog-api.md 5절의 "없음" 항목을 고쳐야 합니다.

### 2.7 SC16IS750(I2C→UART 변환) vs J5 직접 UART

| | J5 직접 UART (권장) | SC16IS750 |
| --- | --- | --- |
| 추가 부품 | 없음 | 변환 모듈 + 배선 |
| 속도 | 하드웨어 UART, 115200bps 여유 | I2C로 FIFO를 계속 읽어야 함. 비전 모듈과 같은 버스면 간섭 |
| 드라이버 | MicroPython 내장 `machine.UART` | 직접 작성해야 함(레지스터 제어) |
| 쓸 이유 | — | J5를 다른 용도로 꼭 써야 할 때만 |

### 2.8 더 빠른 UART(예: 921600bps)를 쓸 수 있는가

- **하드웨어·펌웨어:** 가능. ESP32 하드웨어 UART는 921600bps 이상을 처리하고, GPIO matrix로 IO32/IO33에 연결할 수 있으며,
  순정 펌웨어의 `machine.UART`가 `baudrate`·`rxbuf`를 받습니다 [확인].
- **우리 라이다에는 해당 없음:** RPLIDAR A1M8은 **115200bps 고정**입니다(공개 데이터시트). 921600bps는 다른 라이다로 바꿀 때만 의미가 있습니다.
- **보행과 동시 실행 부담:**

  | 속도 | 초당 데이터 | `rxbuf` 8KB가 차는 시간 | 평가 |
  | --- | --- | --- | --- |
  | 115200bps (A1M8) | 약 11.5KB | 약 0.7초 | 여유 있음 |
  | 921600bps | 약 92KB | 약 0.09초 | Python이 90ms 안에 계속 꺼내 Wi-Fi로 보내야 해서 빠듯함 |

  921600bps에서는 중계 스레드가 CPU를 많이 써서 명령 수신·600ms 통신두절 감시 스레드가 늦어질 위험이 있습니다(안전 문제).
  쓰게 되면 중계 루프에 양보 시간을 두고, 감시 지연을 실측한 뒤 결정합니다.

### 2.9 남는 GPIO와 5V 출력

| 핀·전원 | 사용 | 근거 |
| --- | --- | --- |
| **IO32, IO33 (J5-4, J5-3)** | **유일하게 비어 있는 범용 GPIO** — 라이다 UART로 쓰면 남는 GPIO 없음 | 제조사 회로도, 시리얼 예제 |
| IO0, IO4 (서보 포트 9·10번) | 사용 불가 — 부가 서보가 없어도 순정 서보 드라이버가 10개 채널을 모두 잡아 PWM을 냄. IO0은 부팅 핀 | 제조사 라이브러리 서보 핀 목록 |
| IO12 (회로도 서보 11번) | 사용 불가 — 부팅 시 플래시 전압을 정하는 핀 | ESP32 일반 사양 |
| IO36, IO39 | 사용 불가 — 커넥터에 나와 있지 않음 | 제조사 회로도 |
| I2C 포트 2개 | I2C 장치 전용 | 제조사 회로도 |
| **J5-1 5V** | 신호·소형 센서용. 라이다 전원으로는 실측 전까지 쓰지 않음 | 5절 |

→ 센서를 더 달려면 I2C 방식 센서를 고르고, 라이다 모터 제어(CTRL_MOTO)는 5V에 묶어 항상 켜는 설계를 유지합니다.

## 3. 최종 권장 하드웨어 구성

```text
                 MechDog (로봇 A, B 각각)
 ┌──────────────────────────────────────────────────┐
 │ RPLIDAR A1M8 ──TX──▶ J5-4 (IO32, UART1 RX)        │
 │              ◀─RX─── J5-3 (IO33, UART1 TX)        │
 │              ──GND── J5-2 (GND) ◀── 공통 접지      │
 │ VCC_5V·5V_MOTO·CTRL_MOTO ◀── 별도 5V (1단계)        │
 │                                                    │
 │ 메인 ESP32: main.py                                │
 │   ├ 스레드1: UART1 → TCP 그대로 중계 (A안)          │
 │   ├ 스레드2: Pi 5 명령 수신(UDP) → 공식 API로 이동  │
 │   └ 스레드3: 감시 — 명령 0.5초 끊기면 move(0, 0)    │
 └───────────────── Wi-Fi (전용 공유기) ───────────────┘
                              │
                 Raspberry Pi 5 (고정 위치)
   TCP 수신 → sllidar_ros2(TCP 채널) → /scan → SLAM Toolbox, RViz2
```

## 4. 배선표

근거: Slamtec RPLIDAR A1M8 데이터시트 (2020-10-15, rev 3.0) Figure 2-4·2-5·2-6·2-8·5-2.

**라이다 본체 커넥터는 7핀 하나가 아니라 두 개입니다** [확인, Figure 5-2]:

| 커넥터 | 규격 | 핀(도면 왼쪽→오른쪽) |
| --- | --- | --- |
| 모터 | **1.25mm 간격 3핀**(PH1.25-3P) | 5V_MOTO, CTRL_MOTO, GND_MOTO |
| 측정 코어 | **1.25mm 간격 4핀**(PH1.25-4P) | GND, VCC_5V, RX, TX |

개발 키트 케이블은 이 3핀+4핀을 어댑터 보드 쪽 7핀으로 모아 줍니다(본문 "1.25-pitch 3+4pin to 1.25-pitch 7pin cable").
도면의 왼쪽→오른쪽이 실물 커넥터의 1번→끝 번호와 같은지는 **[확인 필요: 실물 인쇄·선 색]**.

| RPLIDAR 신호 | 커넥터 | MechDog 연결 위치 | 전압 | 기능 | 상태 |
| --- | --- | --- | --- | --- | --- |
| TX (라이다 출력) | 코어 4핀 | **J5-4, IO32** (MechDog RX) | 3.3V TTL, 출력 High 2.9~3.5V | 거리 데이터 수신 | [확인] / 방향 [확인 필요] |
| RX (라이다 입력) | 코어 4핀 | **J5-3, IO33** (MechDog TX) | 3.3V TTL, 입력 High 1.6~3.5V | 명령 전송 | [확인] / 방향 [확인 필요] |
| GND | 코어 4핀 | **J5-2, GND** + 별도 전원 GND | 0V | 공통 접지 | [확인] |
| VCC_5V | 코어 4핀 | **별도 5V**(리플 50mV 이하) | 4.9~**5.5V 최대** | 측정 코어 전원 | [확인] |
| 5V_MOTO | 모터 3핀 | 별도 5V (1단계는 VCC_5V와 같은 전원) | 5~9V | 모터 전원 | [확인] |
| CTRL_MOTO | 모터 3핀 | **5V(VCC_5V)에 연결 → 항상 켬** | 0~5V(최대 5.5V로 보임) | 모터 켜기/PWM | [확인] |
| GND_MOTO | 모터 3핀 | 별도 전원 GND (= J5-2와 공통) | 0V | 모터 접지 | [확인] |

- **CTRL_MOTO는 5V_MOTO가 아니라 5V에 묶습니다.** 모터 전원을 5V보다 높게(예: 배터리 전압) 줄 경우
  CTRL_MOTO 최대값(약 5V)을 넘을 수 있기 때문입니다.
- **J5-1(5V)은 1단계에서 연결하지 않습니다.** 5V 레일의 여유가 확인되지 않았습니다.
- 신호 전압: 라이다는 3.3V TTL UART [확인, 데이터시트 9쪽]. 라이다 TX High(최대 3.5V)는 ESP32 입력 한계(3.6V) 안,
  ESP32 TX(3.3V)는 라이다 RX 범위(1.6~3.5V) 안 → **레벨 변환기 불필요**.
- **라이다 RX에는 직렬 저항을 넣지 않습니다.** 데이터시트 주석: RX는 전류로 신호를 인식하므로 핀 전압이 1.6V 아래로
  떨어지면 안 됨. 라이다 TX → ESP32 RX 쪽에만 보호용 220~330Ω을 넣을 수 있습니다.

## 5. 전원·안전 검토 (7절 요약 포함)

| 항목 | 값 | 근거 |
| --- | --- | --- |
| 배터리 | 7.4V 1500mAh 5C, 충전 8.4V 2A | [공식 명세·충전 근거](hardware-spec.md) |
| 보드 입력 | 6~8.4V | 제조사 기술 사양서 |
| 5V 레일 | 배터리 → RT8289GSP 강압 컨버터 → ESP32 코어 보드, I2C 포트(비전 모듈 포함, 권장 5V 2A), 초음파, J5-1이 함께 사용. 5V 레일에는 TVS만 있고 퓨즈 없음(1A 퓨즈 4개는 서보 전원 쪽) | 제조사 회로도 (V1.2) "ESP32 Module 5V Power Supply Circuit" |
| 5V 레일 최대 전류 | **[확인 필요]** — 칩 정격과 인덕터·발열 한계가 자료에 없음 | — |
| 서보 전원 | VIN(배터리) 직결, 서보 2개마다 1A 퓨즈(F1~F4) | 같은 회로도 |
| 3PIN 전원 포트(P11) | VIN(배터리 전압) 출력 | 같은 회로도 "Servo Expansion Circuit" |
| 라이다 코어 | 4.9~5.5V, 리플 20mV(최대 50mV), **기동 500mA(최대 600mA)**, 동작 300mA(최대 350mA), 대기 80mA | Slamtec 데이터시트 Figure 2-8 [확인] |
| 라이다 모터 | 자료 범위 5~9V, 5V에서 약 100mA. **우리 초기 구성은 별도 5V**, 실제 Hz 측정 | 같은 표, 3쪽 [확인] |
| 라이다 합계 | 동작 약 400~450mA, 기동 순간 최대 약 700mA → **5V 1A 이상 전원** 필요 | 위 값 합산 |
| 라이다 권장 | 코어와 모터 전원을 **분리**해서 공급(데이터 정확도), 코어는 리플 1% 미만 | Figure 2-7 [확인] |
| 비전 모듈 | 5V 2A 이상 권장 | 비전 모듈 설명서 |

권장 순서:
0. **0단계(라이다 단독):** 키트의 USB 어댑터로 Pi 5나 PC에 연결해 라이다가 정상인지 먼저 확인(전원·모터·데이터 모두 USB).
1. **1단계(테스트):** 라이다는 USB 보조배터리(5V 2A 이상) 또는 실험용 전원(5V, 전류 제한 1A)으로 따로 구동. MechDog와는 **GND와 UART 두 선만** 연결.
2. **전류 실측:** 기동 시·정상 회전 시 전류를 측정해 데이터시트 값(합계 약 0.4~0.7A)과 비교해 기록.
3. **2단계(탑재):** 실측값을 보고 결정
   - (권장) **P11(VIN) → 소형 DC-DC 강압(5V, 1A 이상) → 라이다 코어·모터**: 로직 5V 레일에 부담을 주지 않음.
     코어 리플 50mV 이하를 맞추려면 강압 출력에 콘덴서를 충분히 둡니다.
   - MP1584 같은 강압 모듈도 입력 범위·출력 5V·기동 전류·리플·발열을 사용자 실측 후 사용합니다.
     배터리 VIN 직접 공급을 기본 구성으로 사용하지 않습니다.
   - J5-1(5V) 사용: 비전 모듈과 같은 레일이라 여유가 확인될 때만.
4. 서보 노이즈 대책: 라이다 전원 입력에 100~470µF 전해 + 100nF 세라믹 콘덴서, 배선은 짧게, GND는 한 점에서 공통.
5. 배터리 전압이 떨어지면(`Hiwonder.Battery_power()`) Pi 5에 알리고 시연을 멈춥니다.

## 6. Wi-Fi 통신 설계

### 6.1 프로토콜 비교

| | TCP | UDP | MQTT |
| --- | --- | --- | --- |
| 라이다 원시 스트림 | **적합** — 순서 보장, Pi 쪽 공식 드라이버가 TCP 채널 지원 | 손실 시 패킷 경계가 깨져 재동기화 필요 | 브로커 경유 지연·오버헤드, 스트림에 부적합 |
| 이동 명령 | 재전송 때문에 늦은 명령이 뒤늦게 도착할 수 있음 | **적합** — 순번으로 오래된 명령 버림 (공식 군집 제어 예제도 UDP) | 가능하지만 브로커 필요 |
| 대시보드 알림 | — | — | Pi 5 내부에서는 선택 가능 |

**결정: 라이다 = TCP, 명령·상태 = UDP.**

### 6.2 A안(원시 중계) vs B안(ESP32에서 파싱)

| | A안: 원시 UART → TCP | B안: ESP32에서 파싱 |
| --- | --- | --- |
| ESP32 CPU | 낮음(바이트 복사만) | **높음** — MicroPython으로 초당 수천 개 샘플을 파싱하면 걸음·통신 스레드가 밀릴 위험 |
| 메모리 | 수 KB 버퍼 | 한 바퀴 분량 배열 + 파싱 중 객체 생성 → GC 정지 |
| 대역폭 | 115200bps 상한 ≈ 11.5KB/s (≈0.1Mbps) | 비슷하거나 약간 적음 |
| 구현 | 단순. Pi에서 **Slamtec 공식 SDK/ROS 2 드라이버를 그대로 사용** | 프로토콜을 직접 구현하고 검증해야 함 |
| 데이터 손실 | TCP가 보장. 끊기면 재연결 후 드라이버가 재시작 | 파싱 오류를 ESP32에서 디버깅하기 어려움 |
| 모터·명령 | 드라이버가 보내는 명령(스캔 시작·정지)이 그대로 라이다에 전달 | 직접 처리 |

**결정: A안.** MicroPython은 펌웨어(C)를 고칠 수 없으므로 B안의 FreeRTOS 태스크 설계를 적용할 수 없고,
Python 파싱은 부담이 큽니다. Arduino(C++)로 펌웨어 전체를 새로 쓰면 B안도 가능하지만, 공식 MicroPython 펌웨어와
`main.py` 기반 Python API(프로젝트 규칙)를 버려야 하므로 택하지 않습니다(10.3절 참고).

### 6.3 포트·메시지

| 용도 | 방향 | 방식 | 포트(제안) |
| --- | --- | --- | --- |
| 라이다 원시 데이터 | 로봇(서버) ↔ Pi 5(클라이언트) | TCP, 양방향 그대로 | 20108 |
| 이동 명령 | Pi 5 → 로봇 | UDP `CMD|<seq>|<step>|<angle>|$` | 9100 |
| 정지 | Pi 5 → 로봇 | UDP `STOP|<seq>|$` | 9100 |
| 상태 | 로봇 → Pi 5 | UDP `STAT|<id>|<seq>|<battery>|$` (1초마다) | 9101 |

## 7. ESP32 측 구현 (`main.py`, MicroPython)

- 펌웨어는 그대로 두고 `main.py`만 올립니다(Hiwonder Python Editor). **업로드는 사용자 확인 후** 합니다.
- 프로젝트 규칙상 통신 코드는 `robot/comm.py`, 라이다 중계는 `custom_sensors/lidar_bridge.py`로 나누는 것이 맞지만,
  Hiwonder Editor가 파일 여러 개 업로드를 지원하는지 **[확인 필요]** 라서 우선 한 파일 예시로 둡니다.

```python
# main.py — MechDog: RPLIDAR UART→TCP 중계 + Pi 5 명령 수신 + 통신 감시 정지
import time, socket, network, machine
import Hiwonder
from HW_MechDog import MechDog

ROBOT_ID = "A"
SSID = "change-me"          # 실제 값은 커밋하지 않는다
PASSWORD = "change-me"
LIDAR_TCP_PORT = 20108
CMD_UDP_PORT = 9100
CMD_TIMEOUT_MS = 500        # 명령이 이 시간 끊기면 정지

mechdog = MechDog()
last_cmd_ms = time.ticks_ms()
last_seq = -1
moving = False

# --- Wi-Fi ---
wlan = network.WLAN(network.STA_IF)
wlan.active(True)
try:
    wlan.config(pm=network.WLAN.PM_NONE)   # 순정 펌웨어에 상수 있음 [확인], 실제 효과는 실측
except Exception as e:
    print("pm config not supported:", e)
wlan.connect(SSID, PASSWORD)
while not wlan.isconnected():
    time.sleep(0.2)
print("wifi ok", wlan.ifconfig())

# --- 라이다 UART (J5: IO32=RX, IO33=TX) ---
lidar = machine.UART(1, baudrate=115200, rx=32, tx=33, rxbuf=4096)

def lidar_bridge():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", LIDAR_TCP_PORT))
    srv.listen(1)
    while True:
        conn, addr = srv.accept()
        conn.setblocking(False)
        print("lidar client", addr)
        try:
            while True:
                n = lidar.any()
                if n:
                    conn.write(lidar.read(n))       # 라이다 → Pi 5
                try:
                    data = conn.recv(256)           # Pi 5(드라이버 명령) → 라이다
                    if data == b"":
                        break                       # 연결 종료
                    lidar.write(data)
                except OSError:
                    pass                            # 받을 데이터 없음
                time.sleep_ms(5)
        except OSError as e:
            print("lidar link lost", e)
        finally:
            conn.close()

def command_loop():
    global last_cmd_ms, last_seq, moving
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", CMD_UDP_PORT))
    while True:
        data, _ = sock.recvfrom(128)
        try:
            parts = data.decode().split("|")
            kind, seq = parts[0], int(parts[1])
            if seq <= last_seq:
                continue                            # 오래된 명령 버림
            last_seq = seq
            last_cmd_ms = time.ticks_ms()
            if kind == "STOP":
                mechdog.move(0, 0); moving = False
            elif kind == "CMD":
                step = max(-100, min(100, int(parts[2])))   # 문서 범위
                angle = max(-30, min(30, int(parts[3])))
                mechdog.move(step, angle); moving = step != 0 or angle != 0
        except Exception as e:
            print("bad cmd", e)
            mechdog.move(0, 0); moving = False      # 이상하면 멈춘다

def watchdog():
    global moving
    while True:
        if moving and time.ticks_diff(time.ticks_ms(), last_cmd_ms) > CMD_TIMEOUT_MS:
            mechdog.move(0, 0); moving = False
            print("cmd timeout -> stop")
        if not wlan.isconnected():
            mechdog.move(0, 0); moving = False
            wlan.connect(SSID, PASSWORD)            # 자동 재연결 시도
            time.sleep(1)
        time.sleep_ms(100)

Hiwonder.startMain(lidar_bridge)
Hiwonder.startMain(command_loop)
Hiwonder.startMain(watchdog)
```

## 8. Raspberry Pi 5 측 (ROS 2)

### 8.1 권장: Slamtec 공식 ROS 2 드라이버를 TCP 채널로 사용

`sllidar_ros2`는 TCP 채널(`channel_type: tcp`)을 지원합니다. 로봇의 TCP 서버(포트 20108)가 라이다 UART를 그대로 중계하므로
드라이버는 라이다가 네트워크에 직접 붙은 것처럼 동작합니다. **A1M8에서 TCP 채널 동작은 [확인 필요]**(TCP 채널은 원래 네트워크형 모델용).

```bash
# ROS 2 Jazzy 기준 (Pi 5 + Ubuntu 24.04)
mkdir -p ~/ros2_ws/src && cd ~/ros2_ws/src
git clone https://github.com/Slamtec/sllidar_ros2.git
cd ~/ros2_ws && colcon build --symlink-install && source install/setup.bash
ros2 run sllidar_ros2 sllidar_node --ros-args \
  -p channel_type:=tcp -p tcp_ip:=<로봇A_IP> -p tcp_port:=20108 \
  -p frame_id:=laser_a -p angle_compensate:=true -p scan_mode:=Standard \
  -r scan:=/robot_a/scan
```

### 8.2 대안: 가상 시리얼 포트

TCP 채널이 A1M8에서 안 되면 `socat`으로 가상 시리얼 포트를 만들어 시리얼 채널로 씁니다.

```bash
sudo apt install socat
socat pty,link=/tmp/ttyLIDAR_A,raw,echo=0 tcp:<로봇A_IP>:20108 &
ros2 run sllidar_ros2 sllidar_node --ros-args -p serial_port:=/tmp/ttyLIDAR_A \
  -p serial_baudrate:=115200 -p frame_id:=laser_a -r scan:=/robot_a/scan
```

주의: USB 어댑터처럼 DTR로 모터를 켜고 끄는 기능은 없습니다(모터는 CTRL_MOTO 상시 ON).

### 8.3 원시 수신 확인용 스크립트 (ROS 없이)

```python
# pi/raw_check.py — 로봇의 라이다 TCP 스트림에 접속해 스캔을 시작하고 받은 바이트 수를 출력
import socket, sys, time
ip = sys.argv[1]
s = socket.create_connection((ip, 20108), timeout=3)
s.sendall(bytes([0xA5, 0x25])); time.sleep(0.1)   # STOP
s.sendall(bytes([0xA5, 0x20]))                    # SCAN (표준 스캔 시작)
total, t0 = 0, time.time()
while time.time() - t0 < 5:
    total += len(s.recv(4096))
print(f"{total/5:.0f} bytes/s")                   # 정상이면 수 KB/s
s.sendall(bytes([0xA5, 0x25]))
```

### 8.4 SLAM Toolbox · RViz2

```bash
sudo apt install ros-jazzy-slam-toolbox ros-jazzy-rviz2
ros2 launch slam_toolbox online_async_launch.py \
  slam_params_file:=<params.yaml>  # scan_topic: /robot_a/scan, base_frame, odom_frame 설정
rviz2   # Fixed Frame: map, LaserScan 토픽 추가
```

**MechDog에는 바퀴 오도메트리가 없습니다.** SLAM Toolbox는 odom 프레임을 요구하므로 처음에는
`rf2o_laser_odometry`(라이다 기반 오도메트리) 같은 패키지로 odom을 만들어야 합니다 **[확인 필요: 4족 보행 흔들림에서의 성능]**.

## 9. 견적 (예산 150,000원)

**가격은 확인하지 않았습니다.** 아래는 필요 부품 목록이며, 가격·판매처는 구매 전에 확인해 채웁니다.

| 부품 | 규격 | 수량(로봇 1대) | 필요 여부 | 가격 | 비고 |
| --- | --- | --- | --- | --- | --- |
| RPLIDAR A1M8-R6 | 360° 2D, 12m | 1 | 필수 | 약 129,800원(사용자 제시) | 구성: 본체 + USB 어댑터 보드 + 본체 연결 케이블 [확인: 판매처(디바이스마트) 답변] |
| **마이크로 USB 케이블** | USB-A ↔ micro-B, **데이터 전송 지원**(충전 전용 아님) | 1 | 필수 | 확인 필요 | 키트에 미포함 [확인: 판매처 답변]. 0단계 USB 어댑터 시험용, 있으면 보유품 사용 |
| **PH1.25 3핀 피그테일** | 1.25mm 간격 3핀, 한쪽만 커넥터 | 1 | 필수 | 확인 필요 | 라이다 모터 커넥터용. 키트 케이블은 자르지 않음 |
| **PH1.25 4핀 피그테일** | 1.25mm 간격 4핀, 한쪽만 커넥터 | 1 | 필수 | 확인 필요 | 라이다 코어 커넥터용 |
| J5 연결 케이블 | J5 커넥터 형번 확인 후(4핀) | 1 | 필수 | 확인 필요 | 형번 [확인 필요] |
| 점퍼선 암-암 / 암-수 | 2.54mm, 20cm | 각 10가닥 1묶음 | 필수(테스트용) | 확인 필요 | 피그테일 선 끝에 점퍼 단자 압착 또는 납땜 |
| 5V 전원(1단계) | USB 보조배터리(5V 2A 이상) + USB-점퍼 케이블 | 1 | 필수(테스트) | 보유품 사용 가능 | 라이다 기동 최대 약 0.7A |
| DC-DC 강압 모듈(2단계) | 입력 6~9V → 5V, 1A 이상 | 1 | 실측 후 결정 | 확인 필요 | P11(VIN)에서 공급 |
| 3PIN 케이블 | P11용(2.0mm 3핀, 형번 [확인 필요]) | 1 | 2단계 | 확인 필요 | |
| 콘덴서 | 220µF 16V 전해 + 100nF | 1세트 | 권장 | 확인 필요 | 서보 노이즈 대책 |
| 직렬 저항 | 220~330Ω | 1 | 권장 | 확인 필요 | 라이다 TX → ESP32 RX 쪽만. 라이다 RX 쪽에는 넣지 않음 |
| 장착 | 양면 폼테이프 / 케이블타이 | 1 | 필수 | 확인 필요 | 테이프 고정 결정에 따름 |
| 방진 | 실리콘 패드 / 고무 스페이서 | 4 | 권장 | 확인 필요 | 라이다 진동 완화 |

- **예산 300,000원, 로봇 2대 모두 라이다 장착으로 결정.** 디바이스마트 장바구니 기준 약 252,490원(부가세 별도) /
  약 277,700원(부가세 포함). 디바이스마트 가격은 부가세 별도로 표시되므로 합계에 10%를 더해 계산합니다.
- 남는 약 2만 원은 2단계(전류 실측 후) DC-DC 강압 모듈·3PIN 케이블용으로 남겨 둡니다.
- 별도 ESP32 보드는 넣지 않았습니다.

## 10. 단계별 테스트

| 단계 | 하는 일 | 정상 결과 | 실패 시 확인 |
| --- | --- | --- | --- |
| 1. J5 핀 확인 | 멀티미터로 J5 1~4번 측정(전원 ON, 아무것도 연결 안 함) | 1번 ≈5V, 2번 0V | 1번 핀 방향, 보드 버전 |
| 2. 라이다 단독 | 먼저 USB 어댑터로 PC/Pi 5에서 확인 → 다음 피그테일로 별도 5V에 VCC_5V·5V_MOTO, CTRL_MOTO=5V | 모터 회전, 전류 실측(데이터시트 합계 0.4~0.7A) | 커넥터 핀 방향, 전원 극성 |
| 3. UART 루프백 | J5-3·J5-4를 서로 연결, REPL에서 `u=machine.UART(1,baudrate=115200,rx=32,tx=33); u.write(b'hi'); time.sleep(0.1); u.read()` | `b'hi'` | UART 번호·핀 지정 지원 여부, J5 핀 방향 |
| 4. 라이다 응답 | 라이다 연결, `u.write(bytes([0xA5,0x50]))`(GET_INFO) 후 `u.read()` | `A5 5A ...`로 시작하는 응답 | TX/RX 교차, GND 공통 |
| 5. Wi-Fi | `main.py`의 Wi-Fi 부분만 실행 | `wifi ok` + IP | SSID, 2.4GHz 여부, `pm` 지원 |
| 6. 원시 수신 | Pi 5에서 `python3 raw_check.py <IP>` | 수 KB/s | 포트, 방화벽, 스레드 시작 여부 |
| 7. 360° 시각화 | sllidar_ros2 + RViz2 | 주변 벽이 원형으로 보임 | TCP 채널 지원 → 8.2절 socat |
| 8. `/scan` 발행 | `ros2 topic hz /robot_a/scan` | 5~10Hz | 드라이버 로그, scan_mode |
| 9. SLAM | SLAM Toolbox + rf2o | 지도가 쌓임 | odom 프레임, TF |
| 10. 보행 중 | 로봇을 걷게 하면서 7~9 반복 (**사용자 확인 후, 줄 묶은 상태로**) | 걸음 정상, `/scan` 끊김 없음, 명령 끊으면 0.5초 안에 정지 | 걸음 흔들림 → B안 금지, 브리지 보드 재검토 |

## 11. 추가로 확인할 것

1. 보드 회로도 버전(V1.0/V1.2)과 J5 1번 핀 위치, J5 커넥터 형번
2. ~~IO32/IO33의 TX/RX 방향~~ → 제조사 Arduino 시리얼 예제로 확인(IO32=RX, IO33=TX). 첫 연결에서 응답으로 재확인
3. ~~펌웨어의 `machine.UART` 핀·버퍼 지정, `WLAN.PM_NONE` 지원~~ → 순정 펌웨어에서 확인. 실제 동작은 루프백·지연 실측
4. 걸음 궤적 계산이 C인지 Python 래퍼인지(서보 출력은 C 타이머로 확인), 보행 중 라이다 중계 시 걸음 품질
5. MechDog 5V 레일 여유 전류, 라이다 기동·정상 전류 실측(데이터시트: 합계 약 0.4~0.7A)
6. 라이다 3핀·4핀 커넥터의 실물 1번 핀 방향(도면과 같은지), 키트 케이블 선 색
7. sllidar_ros2 TCP 채널이 A1M8 + 중계 구성에서 동작하는지
8. 4족 보행 흔들림에서 라이다 오도메트리·SLAM 품질
9. 로봇 2대분 라이다 예산

## 출처

- 제조사(Hiwonder) 회로도 V1.2, 기술 사양서, Python 시리얼 통신·군집 제어 예제, Arduino 예제 라이브러리 (공개 배포 자료, 저장소 미포함)
- Slamtec RPLIDAR A1M8 데이터시트 rev 3.0 — 커넥터·핀, 신호 전압, 전원·전류
- [Waveshare RPLIDAR A1 위키](https://www.waveshare.com/wiki/RPLIDAR_A1) — 초기 참고(전류 100mA 표기는 데이터시트와 다름)
- [Slamtec A1M8 키트 사용자 매뉴얼](https://bucket-download.slamtec.com/269e60a69933dffb1067a2ee3405f2918168064a/LM108_SLAMTEC_rplidarkit_usermanual_A1M8_v2.1_en.pdf) — 7핀 5267-7A, MOTOCTL (검색 요약 기준, 원문 접근은 403)
- [manuals.plus A1M8 매뉴얼](https://manuals.plus/slamtec/a1m8-rplidar-a1-low-cost-360-degree-laser-range-scanner-manual)
- [Slamtec sllidar_ros2](https://github.com/Slamtec/sllidar_ros2)
