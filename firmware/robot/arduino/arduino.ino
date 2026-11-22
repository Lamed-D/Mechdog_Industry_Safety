// 메인 ESP32 Arduino 펌웨어 — robot/ MicroPython 판(app.py·main.py)의 이식.
// 판단은 Windows 노트북, 동작·정지는 로봇. 명령을 공식 MechDog API 로 실행하고, 끊기면 스스로 멈춥니다.
// 세 태스크(수신·감시·라이다)를 따로 돌리고 뮤텍스로 상태 변경을 직렬화합니다. 감시가 수신과 다른 태스크라
// 수신이 멈춰도 600 ms 뒤 정지합니다(ai/protocol.md 5.1절).
//
// 업로드(굽기)는 사용자만 합니다(ai/firmware.md 1.4절). 이 .ino 를 올리면 순정 MicroPython 이 지워집니다.
// 벤더 라이브러리(HW_MechDog 등)는 저장소에 없으므로 제조사 패키지로 설치해야 컴파일됩니다(README.md).
#include <Arduino.h>
#include "mech_config.h"
#include "mech_core.h"
#include "arduino_clock.h"
#include "motion_mechdog.h"
#include "net_link.h"
#include "lidar_relay.h"

#if __has_include("secrets.h")
#include "secrets.h"
#else
#include "secrets.example.h"  // 실제 값은 secrets.h 에. 없으면 예시(가짜)로 컴파일만 됨.
#endif

using namespace mech;

static Config cfg;
static ArduinoClock sys_clock;
static MechDogHw hw;
static Robot robot(cfg, &hw, &sys_clock, &hw);
static NetLink net(cfg, &sys_clock, MECH_WIFI_SSID, MECH_WIFI_PASS);
static LidarRelay lidar(cfg, &sys_clock);

static SemaphoreHandle_t robot_mtx = nullptr;

static inline void lock() { xSemaphoreTake(robot_mtx, portMAX_DELAY); }
static inline void unlock() { xSemaphoreGive(robot_mtx); }

// 명령 수신 + 텔레메트리 (python/app.py comm_step)
static void comm_task(void*) {
  for (;;) {
    net.service();
    lock();
    robot.set_condition(W_PM_ON, net.pm_on());
    uint8_t buf[256];
    uint32_t ip = 0;
    int n, guard = 0;
    while ((n = net.recv(buf, sizeof(buf), ip)) >= 0 && guard++ < 16)
      robot.handle(buf, (size_t)n, ip);

    bool due = robot.telemetry_due();
    char line[200];
    char role[100];
    size_t L = 0, RL = 0;
    uint32_t dip = 0;
    if (due) {
      L = robot.telemetry(line, sizeof(line));
      RL = robot.role_status(role, sizeof(role));
      dip = robot.telemetry_dest_ip();
    }
    unlock();

    if (due && L && dip) {
      net.send(line, L, dip, cfg.TEL_PORT);
      if (RL) net.send(role, RL, dip, cfg.TEL_PORT);  // 역할 상태(ai/protocol.md)
    }
    vTaskDelay(pdMS_TO_TICKS(5));
  }
}

// 감시: 통신 끊김·저전압·이동 유효시간 정지 (python/app.py watchdog_step)
static void watchdog_task(void*) {
  for (;;) {
    bool up = net.connected();
    lock();
    robot.tick(up);
    unlock();
    vTaskDelay(pdMS_TO_TICKS(cfg.WATCHDOG_PERIOD_MS));
  }
}

// 라이다 원시 중계. 라이다 문제로 로봇을 멈추지 않음(ai/protocol.md 7절).
static void lidar_task(void*) {
  for (;;) {
    lidar.service(net.connected());
    lock();
    robot.set_condition(W_LIDAR_UART, !lidar.uart_ok());
    robot.set_condition(W_LIDAR_BACKLOG, lidar.backlogged());
    unlock();
    vTaskDelay(pdMS_TO_TICKS(2));
  }
}

void setup() {
  Serial.begin(115200);
  cfg.ROBOT_ID = MECH_ROBOT_ID;

  robot_mtx = xSemaphoreCreateMutex();

  hw.begin();     // MechDog 초기화 + 동작 워커 태스크 + 초기 정지
  net.begin();    // Wi-Fi STA
  lidar.begin();  // 라이다 UART

  lock();
  robot.set_condition(W_PM_ON, net.pm_on());
  robot.set_condition(W_LIDAR_UART, !lidar.uart_ok());
  unlock();

  // 앱 태스크는 core 1 에(WiFi 스택은 core 0). 감시 우선순위를 가장 높게.
  xTaskCreatePinnedToCore(watchdog_task, "watchdog", 4096, nullptr, 3, nullptr, APP_CPU_NUM);
  xTaskCreatePinnedToCore(comm_task, "comm", 6144, nullptr, 2, nullptr, APP_CPU_NUM);
  xTaskCreatePinnedToCore(lidar_task, "lidar", 4096, nullptr, 2, nullptr, APP_CPU_NUM);
}

void loop() {
  // 세팅·점검용: Wi-Fi 에 붙으면 로봇 IP 를 한 번 시리얼로 알립니다(콘솔 --robot-ip 지정에 참고).
  static bool shown = false;
  if (WiFi.status() == WL_CONNECTED) {
    if (!shown) {
      Serial.print("WiFi OK  id=");
      Serial.print((char)cfg.ROBOT_ID);
      Serial.print("  ip=");
      Serial.println(WiFi.localIP());
      shown = true;
    }
  } else {
    shown = false;
  }
  vTaskDelay(pdMS_TO_TICKS(1000));
}
