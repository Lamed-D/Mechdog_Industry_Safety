// MechDog 비전 모듈(ESP32-S3 카메라) 맞춤 펌웨어.
// - 전용 공유기에 STA로 붙어 Pi 5에 영상을 보냅니다(:81/stream MJPEG, :80/capture, :80/status).
// - 메인 보드의 공식 ESP32S3Cam I2C 읽기에는 규격대로 "결과 없음"으로 응답합니다(인식은 Pi 5가 함).
// - 이 펌웨어는 로봇을 움직이지 않습니다. 카메라 모듈 안에서만 동작합니다.
// - 로봇 ID·Wi-Fi 는 USB 시리얼 명령(help)으로 저장하거나 secrets.h 로 빌드합니다.
// 빌드·굽기·복구: docs/vision-cam-firmware.md

#include "config.h"
#include "esp_task_wdt.h"
#include "frame_store.h"
#include "http_api.h"
#include "i2c_compat.h"
#include "net.h"
#include "settings.h"

static void start_watchdog() {
  // 코어가 이미 켠 작업 워치독의 시간을 늘리고, loop 작업을 감시 대상에 넣습니다.
  esp_task_wdt_config_t cfg = {};
  cfg.timeout_ms = CAM_WDT_TIMEOUT_MS;
  cfg.idle_core_mask = 1 << 0;  // 코어 0(Wi-Fi·HTTP·스트림)이 막히면 감지
  cfg.trigger_panic = true;  // 멈추면 재부팅
  if (esp_task_wdt_reconfigure(&cfg) != ESP_OK) esp_task_wdt_init(&cfg);
  esp_task_wdt_add(nullptr);
}

void setup() {
  Serial.begin(115200);
  start_watchdog();
  settings_begin();  // 로봇 ID·Wi-Fi 를 먼저 읽어야 이름·접속이 정해짐
  Serial.printf("[cam] fw %s robot %s secrets.h=%d\n", CAM_FW_VERSION, settings_robot(), CAM_HAS_SECRETS);

  bool cam = frame_store_begin();
  Serial.printf("[cam] camera %s, psram %s\n", cam ? "ok" : "FAILED (retrying)", psramFound() ? "yes" : "no");

  bool i2c = i2c_compat_begin();
  Serial.printf("[cam] i2c slave 0x%02X %s\n", CAM_I2C_ADDR, i2c ? "ok" : "FAILED");

  net_begin();
  bool http = http_begin();
  Serial.printf("[cam] http :%d/:%d %s, host %s\n", CAM_HTTP_PORT, CAM_STREAM_PORT, http ? "ok" : "FAILED",
                net_hostname());
}

void loop() {
  esp_task_wdt_reset();
  settings_poll_serial();
  net_loop();

  CamStats st = frame_store_stats();
  int clients = http_stream_clients();

  static uint32_t last_log = 0;
  if (millis() - last_log >= 10000) {
    last_log = millis();
    char ip[16];
    net_ip(ip, sizeof(ip));
    Serial.printf("[cam] %s %s rssi %d | cam %d fps %.1f clients %d | heap %u\n", net_mode(), ip, net_rssi(),
                  st.camera_ok, st.fps, clients, (unsigned)ESP.getFreeHeap());
  }
  delay(20);
}
