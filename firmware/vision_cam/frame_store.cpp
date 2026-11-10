#include "frame_store.h"

#include <Arduino.h>
#include <string.h>

#include <atomic>

#include "cam_board.h"
#include "config.h"
#include "esp_camera.h"
#include "esp_heap_caps.h"
#include "esp_system.h"
#include "esp_task_wdt.h"
#include "esp_timer.h"
#include "img_converters.h"

// 카메라 재초기화가 계속 실패해 재부팅한 횟수. 전원이 꺼지기 전까지 유지됩니다.
// 카메라가 아예 없을 때 재부팅이 끝없이 반복되지 않도록, 이 횟수를 넘기면 재부팅 대신 느리게 재시도합니다.
#define CAM_RESTART_MAGIC 0x43414D31u
RTC_NOINIT_ATTR static uint32_t s_restart_magic;
RTC_NOINIT_ATTR static uint32_t s_restart_count;
#define CAM_MAX_RESTARTS 3

static SemaphoreHandle_t s_lock;
static uint8_t *s_buf;
static size_t s_cap;
static size_t s_len;
static uint32_t s_seq;
static int64_t s_ts_us;
// 마지막 요청 시각(ms). 여러 코어에서 쓰고 읽으므로 32비트 원자 변수(64비트는 찢어져 읽힐 수 있음).
static std::atomic<uint32_t> s_demand_ms{0};
static CamStats s_stats;
// 센서가 JPEG 를 못 만든다는 것을 한 번 확인하면, 재초기화 때 JPEG 시도(오류 로그)를 반복하지 않습니다.
static bool s_sensor_no_jpeg;

static void apply_orientation(sensor_t *s) {
  int vflip = 0;
  int hmirror = -1;  // -1: 센서 기본값 유지
  uint16_t pid = s->id.PID;
  if (pid == OV2640_PID || pid == OV3660_PID || pid == GC032A_PID) vflip = 1;
  if (pid == GC0308_PID) hmirror = 0;
  if (CAM_VFLIP >= 0) vflip = CAM_VFLIP;
  if (CAM_HMIRROR >= 0) hmirror = CAM_HMIRROR;
  if (s->set_vflip) s->set_vflip(s, vflip);
  if (hmirror >= 0 && s->set_hmirror) s->set_hmirror(s, hmirror);
}

static bool camera_init() {
  camera_config_t c = {};
  c.pin_pwdn = CAM_PIN_PWDN;
  c.pin_reset = CAM_PIN_RESET;
  c.pin_xclk = CAM_PIN_XCLK;
  c.pin_sccb_sda = CAM_PIN_SIOD;
  c.pin_sccb_scl = CAM_PIN_SIOC;
  c.pin_d0 = CAM_PIN_D0;
  c.pin_d1 = CAM_PIN_D1;
  c.pin_d2 = CAM_PIN_D2;
  c.pin_d3 = CAM_PIN_D3;
  c.pin_d4 = CAM_PIN_D4;
  c.pin_d5 = CAM_PIN_D5;
  c.pin_d6 = CAM_PIN_D6;
  c.pin_d7 = CAM_PIN_D7;
  c.pin_vsync = CAM_PIN_VSYNC;
  c.pin_href = CAM_PIN_HREF;
  c.pin_pclk = CAM_PIN_PCLK;
  c.xclk_freq_hz = CAM_XCLK_HZ;
  c.ledc_timer = LEDC_TIMER_0;
  c.ledc_channel = LEDC_CHANNEL_0;
  c.pixel_format = PIXFORMAT_JPEG;
  c.jpeg_quality = CAM_JPEG_QUALITY;

  // PSRAM 이 없으면 내부 메모리에 맞게 작은 해상도·버퍼 1개로 낮춥니다.
  bool ps = psramFound();
  c.frame_size = ps ? CAM_FRAME_SIZE : FRAMESIZE_QVGA;
  c.fb_count = ps ? CAM_FB_COUNT : 1;
  c.fb_location = ps ? CAMERA_FB_IN_PSRAM : CAMERA_FB_IN_DRAM;
  c.grab_mode = ps ? CAMERA_GRAB_LATEST : CAMERA_GRAB_WHEN_EMPTY;

  // 센서에 JPEG 압축기가 없으면 드라이버가 ESP_ERR_NOT_SUPPORTED 로 거절합니다(실패 시 드라이버가 스스로 정리).
  // 그때는 RGB565 로 다시 열고 칩에서 압축합니다. RGB565 VGA 버퍼(약 600KB)는 PSRAM 이 있어야 둡니다.
  bool soft = s_sensor_no_jpeg;
  esp_err_t err = ESP_FAIL;
  if (!soft) {
    err = esp_camera_init(&c);
    if (err == ESP_ERR_NOT_SUPPORTED) {
      s_sensor_no_jpeg = soft = true;
      Serial.println("[cam] sensor has no JPEG encoder, using RGB565 + software JPEG");
    }
  }
  if (soft) {
    if (!ps) return false;
    c.pixel_format = PIXFORMAT_RGB565;
    err = esp_camera_init(&c);
  }
  if (err != ESP_OK) return false;
  sensor_t *s = esp_camera_sensor_get();
  if (s == nullptr) {
    esp_camera_deinit();
    return false;
  }
  apply_orientation(s);
  camera_sensor_info_t *info = esp_camera_sensor_get_info(&s->id);

  xSemaphoreTake(s_lock, portMAX_DELAY);
  s_stats.psram = ps;
  s_stats.width = resolution[c.frame_size].width;
  s_stats.height = resolution[c.frame_size].height;
  s_stats.quality = (uint8_t)c.jpeg_quality;
  s_stats.soft_jpeg = soft;
  s_stats.sensor = info ? info->name : "unknown";
  s_stats.camera_ok = true;
  s_stats.dimensions_measured = false;
  xSemaphoreGive(s_lock);
  Serial.printf("[cam] sensor %s (PID 0x%04X), %s\n", info ? info->name : "unknown", (unsigned)s->id.PID,
                soft ? "software JPEG" : "sensor JPEG");
  return true;
}

static void camera_lost() {
  esp_camera_deinit();
  xSemaphoreTake(s_lock, portMAX_DELAY);
  s_stats.camera_ok = false;
  s_stats.dimensions_measured = false;
  s_stats.reinits++;
  xSemaphoreGive(s_lock);
}

static bool store_frame(const uint8_t *buf, size_t len, uint16_t width, uint16_t height, int64_t now_us) {
  xSemaphoreTake(s_lock, portMAX_DELAY);
  if (len > s_cap) {
    size_t want = len + len / 4;
    uint8_t *grown = (uint8_t *)heap_caps_realloc(s_buf, want, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
    if (grown == nullptr) grown = (uint8_t *)realloc(s_buf, want);
    if (grown == nullptr) {
      xSemaphoreGive(s_lock);
      return false;
    }
    s_buf = grown;
    s_cap = want;
  }
  memcpy(s_buf, buf, len);
  s_len = len;
  s_seq++;
  s_ts_us = now_us;
  s_stats.frames++;
  s_stats.last_frame_us = now_us;
  s_stats.last_len = len;
  s_stats.width = width;
  s_stats.height = height;
  s_stats.dimensions_measured = true;
  xSemaphoreGive(s_lock);
  return true;
}

static bool jpeg_bytes_ok(const uint8_t *buf, size_t len) {
  return buf != nullptr && len > 4 && buf[0] == 0xFF && buf[1] == 0xD8 && buf[len - 2] == 0xFF && buf[len - 1] == 0xD9;
}

// 센서 프레임이 쓸 수 있는 모양인지: JPEG 모드는 JPEG 바이트, 소프트 모드는 크기가 맞는 RGB565.
static bool frame_ok(const camera_fb_t *fb, bool soft) {
  if (fb->width == 0 || fb->height == 0) return false;
  if (soft) return fb->format == PIXFORMAT_RGB565 && fb->len == (size_t)fb->width * fb->height * 2;
  return fb->format == PIXFORMAT_JPEG && jpeg_bytes_ok(fb->buf, fb->len);
}

static void capture_task(void *) {
  esp_task_wdt_add(nullptr);
  uint32_t fails = 0;
  uint32_t init_fails = 0;
  uint32_t drop = 0;
  bool was_idle = true;
  uint32_t window_frames = 0;
  uint32_t window_bytes = 0;
  int64_t window_start = esp_timer_get_time();

  for (;;) {
    esp_task_wdt_reset();
    int64_t now = esp_timer_get_time();
    int64_t cycle_start = now;

    if (!frame_store_stats().camera_ok) {
      if (camera_init()) {
        init_fails = 0;
        s_restart_count = 0;
        continue;
      }
      init_fails++;
      bool may_restart = s_restart_magic != CAM_RESTART_MAGIC || s_restart_count < CAM_MAX_RESTARTS;
      if (init_fails >= CAM_REINITS_BEFORE_RESTART && may_restart) {
        if (s_restart_magic != CAM_RESTART_MAGIC) {
          s_restart_magic = CAM_RESTART_MAGIC;
          s_restart_count = 0;
        }
        s_restart_count++;
        esp_restart();
      }
      // 재부팅 한도를 넘었으면 상태 확인이 가능하도록 살아 있으면서 30초마다 다시 시도합니다.
      for (int i = 0; i < (may_restart ? 1 : 30); i++) {
        esp_task_wdt_reset();
        vTaskDelay(pdMS_TO_TICKS(1000));
      }
      continue;
    }

    bool idle = (uint32_t)(now / 1000) - s_demand_ms.load() > (uint32_t)CAM_IDLE_MS;
    if (idle) {
      if (!was_idle) {
        xSemaphoreTake(s_lock, portMAX_DELAY);
        s_stats.idle = true;
        s_stats.fps = 0;
        s_stats.kbps = 0;
        xSemaphoreGive(s_lock);
      }
      was_idle = true;
      vTaskDelay(pdMS_TO_TICKS(50));
      continue;
    }
    if (was_idle) {
      // 쉬는 동안 버퍼에 남은 옛 프레임을 버립니다.
      drop = CAM_FB_COUNT;
      was_idle = false;
      window_frames = 0;
      window_bytes = 0;
      window_start = now;
      xSemaphoreTake(s_lock, portMAX_DELAY);
      s_stats.idle = false;
      xSemaphoreGive(s_lock);
    }

    bool soft = s_sensor_no_jpeg;
    camera_fb_t *fb = esp_camera_fb_get();
    uint8_t *jpg = nullptr;
    size_t jpg_len = 0;
    bool ok = fb != nullptr && frame_ok(fb, soft);
    if (ok && soft && drop == 0) {
      // 버리는 프레임은 변환하지 않습니다. 변환 실패·깨진 결과는 촬영 실패로 셉니다.
      ok = frame2jpg(fb, CAM_SOFT_JPEG_QUALITY, &jpg, &jpg_len) && jpeg_bytes_ok(jpg, jpg_len);
      if (!ok) {
        free(jpg);
        jpg = nullptr;
      }
    }
    if (!ok) {
      if (fb) esp_camera_fb_return(fb);
      fails++;
      xSemaphoreTake(s_lock, portMAX_DELAY);
      s_stats.failures++;
      xSemaphoreGive(s_lock);
      if (fails >= CAM_FAILS_BEFORE_REINIT) {
        fails = 0;
        camera_lost();
      }
      vTaskDelay(pdMS_TO_TICKS(10));
      continue;
    }
    fails = 0;
    if (drop > 0) {
      drop--;
      esp_camera_fb_return(fb);
      continue;
    }
    now = esp_timer_get_time();
    // 버퍼를 복사한 시각이 아니라 드라이버가 기록한 실제 취득 시각을 전달합니다.
    int64_t captured = (int64_t)fb->timestamp.tv_sec * 1000000 + fb->timestamp.tv_usec;
    const uint8_t *out = soft ? jpg : fb->buf;
    size_t frame_bytes = soft ? jpg_len : fb->len;
    bool stored = captured > 0 && captured <= now &&
                  store_frame(out, frame_bytes, (uint16_t)fb->width, (uint16_t)fb->height, captured);
    esp_camera_fb_return(fb);
    free(jpg);
    if (stored) {
      window_frames++;
      window_bytes += frame_bytes;
    }

    if (now - window_start >= 1000000) {
      float fps = window_frames * 1000000.0f / (float)(now - window_start);
      xSemaphoreTake(s_lock, portMAX_DELAY);
      s_stats.fps = fps;
      s_stats.kbps = window_bytes * 8000.0f / (float)(now - window_start);
      xSemaphoreGive(s_lock);
      window_frames = 0;
      window_bytes = 0;
      window_start = now;
    }
    // 센서는 최신 버퍼를 계속 갱신합니다. 전송용 사본 생성 속도만 제한합니다.
    // 소프트웨어 JPEG 처럼 한 주기가 목표 간격보다 길어도 매번 잠깐 쉽니다. 쉬지 않으면 같은 코어의
    // Arduino loop(Wi-Fi 재접속·시리얼 설정·워치독 갱신)가 굶어 작업 워치독이 재부팅시킵니다(실물에서 확인).
    int64_t wait_us = 1000000 / CAM_TARGET_FPS - (esp_timer_get_time() - cycle_start);
    if (wait_us < (int64_t)CAM_MIN_YIELD_MS * 1000) wait_us = (int64_t)CAM_MIN_YIELD_MS * 1000;
    vTaskDelay(pdMS_TO_TICKS((uint32_t)(wait_us / 1000)));
  }
}

bool frame_store_begin() {
  s_lock = xSemaphoreCreateMutex();
  memset(&s_stats, 0, sizeof(s_stats));
  s_stats.sensor = "none";
  s_stats.idle = true;
  if (esp_reset_reason() == ESP_RST_POWERON) s_restart_magic = 0;  // 전원을 새로 켜면 횟수 초기화
  bool ok = camera_init();
  if (ok) s_restart_count = 0;
  // 촬영 작업은 Wi-Fi(코어 0)와 다른 코어 1에서 돌립니다.
  xTaskCreatePinnedToCore(capture_task, "cam_capture", 6144, nullptr, 5, nullptr, 1);
  return ok;
}

void frame_store_demand() { s_demand_ms.store((uint32_t)(esp_timer_get_time() / 1000)); }

uint32_t frame_store_seq() {
  xSemaphoreTake(s_lock, portMAX_DELAY);
  uint32_t seq = s_seq;
  xSemaphoreGive(s_lock);
  return seq;
}

size_t frame_store_copy(uint8_t *dst, size_t cap, uint32_t after_seq, uint32_t timeout_ms,
                        uint32_t *seq_out, int64_t *ts_us_out, size_t *need) {
  int64_t deadline = esp_timer_get_time() + (int64_t)timeout_ms * 1000;
  if (need) *need = 0;
  for (;;) {
    frame_store_demand();
    xSemaphoreTake(s_lock, portMAX_DELAY);
    if (s_stats.camera_ok && s_len > 0 && s_seq != after_seq &&
        esp_timer_get_time() - s_ts_us <= (int64_t)CAM_FRAME_WAIT_MS * 1000) {
      if (s_len > cap) {
        if (need) *need = s_len;
        xSemaphoreGive(s_lock);
        return 0;
      }
      memcpy(dst, s_buf, s_len);
      size_t len = s_len;
      if (seq_out) *seq_out = s_seq;
      if (ts_us_out) *ts_us_out = s_ts_us;
      xSemaphoreGive(s_lock);
      return len;
    }
    xSemaphoreGive(s_lock);
    if (esp_timer_get_time() >= deadline) return 0;
    vTaskDelay(pdMS_TO_TICKS(5));
  }
}

CamStats frame_store_stats() {
  xSemaphoreTake(s_lock, portMAX_DELAY);
  CamStats copy = s_stats;
  xSemaphoreGive(s_lock);
  return copy;
}
