#include "http_api.h"

#include <Arduino.h>
#include <atomic>

#include "config.h"
#include "esp_heap_caps.h"
#include "esp_http_server.h"
#include "esp_timer.h"
#include "frame_store.h"
#include "i2c_compat.h"
#include "net.h"
#include "settings.h"

#define STREAM_BOUNDARY "mechdogframe"
#define FIRST_BUF_BYTES (64 * 1024)

static httpd_handle_t s_http = nullptr;
static httpd_handle_t s_stream = nullptr;
static std::atomic<int> s_clients{0};

// ── 공통 ──

static bool key_ok(httpd_req_t *req) {
  const char *want = settings_key();
  if (want[0] == '\0') return true;
  char query[128];
  char got[72];
  if (httpd_req_get_url_query_str(req, query, sizeof(query)) != ESP_OK) return false;
  if (httpd_query_key_value(query, "key", got, sizeof(got)) != ESP_OK) return false;
  size_t n = strlen(want);
  if (strlen(got) != n) return false;
  uint8_t diff = 0;  // 길이가 같으면 끝까지 비교(응답 시간으로 키를 추측하기 어렵게)
  for (size_t i = 0; i < n; i++) diff |= (uint8_t)(want[i] ^ got[i]);
  return diff == 0;
}

static esp_err_t send_text(httpd_req_t *req, const char *status, const char *text) {
  httpd_resp_set_status(req, status);
  httpd_resp_set_type(req, "text/plain");
  httpd_resp_set_hdr(req, "Cache-Control", "no-store");
  if (status[0] != '2') httpd_resp_set_hdr(req, "Connection", "close");  // 거절한 연결이 자리를 차지하지 않게
  return httpd_resp_sendstr(req, text);
}

static uint8_t *grow(uint8_t *buf, size_t *cap, size_t need) {
  size_t want = need + need / 4;
  uint8_t *p = (uint8_t *)heap_caps_realloc(buf, want, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
  if (p == nullptr) p = (uint8_t *)realloc(buf, want);
  if (p == nullptr) return buf;  // 실패하면 기존 버퍼 유지(호출한 쪽이 cap 으로 판단)
  *cap = want;
  return p;
}

static uint8_t *alloc_buf(size_t *cap) {
  uint8_t *p = (uint8_t *)heap_caps_malloc(FIRST_BUF_BYTES, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
  *cap = FIRST_BUF_BYTES;
  if (p == nullptr) {  // PSRAM 이 없으면 내부 메모리에 작게
    p = (uint8_t *)malloc(FIRST_BUF_BYTES / 2);
    *cap = FIRST_BUF_BYTES / 2;
  }
  if (p == nullptr) *cap = 0;
  return p;
}

// 새 프레임을 buf 로 가져옵니다. 버퍼가 작으면 키워서 다시 시도합니다. 실패하면 0.
static size_t fetch(uint8_t **buf, size_t *cap, uint32_t after, uint32_t wait_ms, uint32_t *seq, int64_t *ts) {
  for (int tries = 0; tries < 3; tries++) {
    size_t need = 0;
    size_t len = frame_store_copy(*buf, *cap, after, wait_ms, seq, ts, &need);
    if (len > 0) return len;
    if (need == 0) return 0;  // 시간 초과
    size_t before = *cap;
    *buf = grow(*buf, cap, need);
    if (*cap == before) return 0;  // 메모리 부족
  }
  return 0;
}

static uint32_t age_ms(int64_t ts_us) {
  int64_t d = esp_timer_get_time() - ts_us;
  return d > 0 ? (uint32_t)(d / 1000) : 0;
}

// ── :80 ──

static esp_err_t index_handler(httpd_req_t *req) {
  if (!key_ok(req)) return send_text(req, "401 Unauthorized", "key required\n");
  char text[256];
  snprintf(text, sizeof(text),
           "MechDog vision camera %s (robot %s)\n"
           "GET /status   JSON\n"
           "GET /capture  JPEG\n"
           "GET :%d/stream  MJPEG (latest frame only)\n",
           CAM_FW_VERSION, settings_robot(), CAM_STREAM_PORT);
  return send_text(req, "200 OK", text);
}

static esp_err_t status_handler(httpd_req_t *req) {
  if (!key_ok(req)) return send_text(req, "401 Unauthorized", "key required\n");
  CamStats st = frame_store_stats();
  char ip[16];
  net_ip(ip, sizeof(ip));
  long frame_age = st.last_frame_us > 0 ? (long)age_ms(st.last_frame_us) : -1;
  char json[900];
  snprintf(json, sizeof(json),
           "{\"robot\":\"%s\",\"host\":\"%s\",\"fw\":\"%s\",\"uptime_s\":%lu,"
           "\"wifi\":{\"mode\":\"%s\",\"ip\":\"%s\",\"rssi\":%d,\"reconnects\":%lu},"
           "\"camera\":{\"ok\":%s,\"sensor\":\"%s\",\"psram\":%s,\"width\":%u,\"height\":%u,"
           "\"quality\":%u,\"fps\":%.1f,\"idle\":%s,\"frames\":%lu,\"failures\":%lu,\"reinits\":%lu,"
           "\"frame_age_ms\":%ld,\"frame_bytes\":%u},"
           "\"stream\":{\"port\":%d,\"clients\":%d,\"max_clients\":%d},"
           "\"memory\":{\"heap_free\":%u,\"psram_free\":%u},"
           "\"i2c\":{\"addr\":%u,\"requests\":%lu},\"recognition\":false,\"auth\":%s}",
           settings_robot(), net_hostname(), CAM_FW_VERSION, (unsigned long)(esp_timer_get_time() / 1000000),
           net_mode(), ip, net_rssi(), (unsigned long)net_sta_reconnects(),
           st.camera_ok ? "true" : "false", st.sensor ? st.sensor : "unknown", st.psram ? "true" : "false",
           st.width, st.height, st.quality, st.fps, st.idle ? "true" : "false", (unsigned long)st.frames,
           (unsigned long)st.failures, (unsigned long)st.reinits, frame_age, (unsigned)st.last_len,
           CAM_STREAM_PORT, http_stream_clients(), CAM_MAX_STREAM_CLIENTS,
           (unsigned)heap_caps_get_free_size(MALLOC_CAP_INTERNAL),
           (unsigned)heap_caps_get_free_size(MALLOC_CAP_SPIRAM), (unsigned)CAM_I2C_ADDR,
           (unsigned long)i2c_compat_requests(), settings_key()[0] ? "true" : "false");
  httpd_resp_set_type(req, "application/json");
  httpd_resp_set_hdr(req, "Cache-Control", "no-store");
  return httpd_resp_sendstr(req, json);
}

static uint8_t *s_capture_buf = nullptr;  // :80 서버는 요청을 하나씩 처리하므로 버퍼 하나를 같이 씀
static size_t s_capture_cap = 0;

static esp_err_t capture_handler(httpd_req_t *req) {
  if (!key_ok(req)) return send_text(req, "401 Unauthorized", "key required\n");
  if (s_capture_buf == nullptr) s_capture_buf = alloc_buf(&s_capture_cap);
  if (s_capture_buf == nullptr) return send_text(req, "503 Service Unavailable", "no memory\n");
  uint32_t seq = 0;
  int64_t ts = 0;
  // 요청 뒤에 찍힌 프레임만 보냅니다(쉬고 있던 카메라의 옛 프레임 방지).
  size_t len = fetch(&s_capture_buf, &s_capture_cap, frame_store_seq(), CAM_CAPTURE_WAIT_MS, &seq, &ts);
  if (len == 0) return send_text(req, "503 Service Unavailable", "no frame\n");
  char seq_text[12], age_text[12], ts_text[22];
  snprintf(seq_text, sizeof(seq_text), "%lu", (unsigned long)seq);
  snprintf(age_text, sizeof(age_text), "%lu", (unsigned long)age_ms(ts));
  snprintf(ts_text, sizeof(ts_text), "%llu", (unsigned long long)(ts / 1000));
  httpd_resp_set_type(req, "image/jpeg");
  httpd_resp_set_hdr(req, "Cache-Control", "no-store");
  httpd_resp_set_hdr(req, "X-Robot", settings_robot());
  httpd_resp_set_hdr(req, "X-Frame-Seq", seq_text);
  httpd_resp_set_hdr(req, "X-Frame-Age-Ms", age_text);
  httpd_resp_set_hdr(req, "X-Timestamp-Ms", ts_text);
  return httpd_resp_send(req, (const char *)s_capture_buf, len);
}

// ── :81 /stream ──

static void stream_task(void *arg) {
  httpd_req_t *req = (httpd_req_t *)arg;
  size_t cap = 0;
  uint8_t *buf = alloc_buf(&cap);
  if (buf != nullptr) {
    httpd_resp_set_type(req, "multipart/x-mixed-replace;boundary=" STREAM_BOUNDARY);
    httpd_resp_set_hdr(req, "Cache-Control", "no-store");
    httpd_resp_set_hdr(req, "X-Robot", settings_robot());
    uint32_t seq = frame_store_seq();  // 재접속 시 쉬던 카메라의 옛 프레임을 보내지 않음
    for (;;) {
      int64_t ts = 0;
      uint32_t next = 0;
      // 보내는 동안 쌓인 프레임은 건너뛰고 가장 최신 것만 가져옵니다.
      size_t len = fetch(&buf, &cap, seq, CAM_FRAME_WAIT_MS, &next, &ts);
      if (len == 0) break;
      seq = next;
      char head[200];
      int n = snprintf(head, sizeof(head),
                       "\r\n--" STREAM_BOUNDARY "\r\nContent-Type: image/jpeg\r\nContent-Length: %u\r\n"
                       "X-Frame-Seq: %lu\r\nX-Frame-Age-Ms: %lu\r\nX-Timestamp-Ms: %llu\r\n\r\n",
                       (unsigned)len, (unsigned long)seq, (unsigned long)age_ms(ts),
                       (unsigned long long)(ts / 1000));
      if (httpd_resp_send_chunk(req, head, n) != ESP_OK) break;
      if (httpd_resp_send_chunk(req, (const char *)buf, len) != ESP_OK) break;
    }
    free(buf);
  }
  // 스트림이 끝나면(카메라 시간 초과·수신자 끊김) 연결을 닫아 다음 수신자가 바로 붙을 수 있게 합니다.
  httpd_sess_trigger_close(req->handle, httpd_req_to_sockfd(req));
  httpd_req_async_handler_complete(req);
  s_clients--;
  vTaskDelete(nullptr);
}

static esp_err_t stream_handler(httpd_req_t *req) {
  if (!key_ok(req)) return send_text(req, "401 Unauthorized", "key required\n");
  int now = s_clients.load();
  do {
    if (now >= CAM_MAX_STREAM_CLIENTS) return send_text(req, "503 Service Unavailable", "stream busy\n");
  } while (!s_clients.compare_exchange_weak(now, now + 1));

  httpd_req_t *copy = nullptr;
  if (httpd_req_async_handler_begin(req, &copy) != ESP_OK) {
    s_clients--;
    return send_text(req, "500 Internal Server Error", "stream start failed\n");
  }
  // 수신자마다 작업 하나. 느린 수신자가 다른 수신자를 막지 않습니다.
  if (xTaskCreatePinnedToCore(stream_task, "cam_stream", 6144, copy, 4, nullptr, 0) != pdPASS) {
    httpd_req_async_handler_complete(copy);
    s_clients--;
    return ESP_FAIL;
  }
  frame_store_demand();
  return ESP_OK;
}

static bool start(httpd_handle_t *h, uint16_t port, uint16_t ctrl, int sockets, const httpd_uri_t *uris, int n) {
  if (*h != nullptr) return true;
  httpd_config_t cfg = HTTPD_DEFAULT_CONFIG();
  cfg.server_port = port;
  cfg.ctrl_port = ctrl;
  cfg.max_open_sockets = sockets;
  cfg.lru_purge_enable = false;  // 진행 중인 스트림 연결을 강제로 닫지 않음
  cfg.send_wait_timeout = 5;     // 수신자가 멈추면 5초 뒤 끊음
  cfg.recv_wait_timeout = 5;
  cfg.stack_size = 6144;
  cfg.core_id = 0;
  if (httpd_start(h, &cfg) != ESP_OK) return false;
  for (int i = 0; i < n; i++) {
    if (httpd_register_uri_handler(*h, &uris[i]) != ESP_OK) {
      httpd_stop(*h);
      *h = nullptr;
      return false;
    }
  }
  return true;
}

bool http_begin() {
  static const httpd_uri_t api[] = {
      {.uri = "/", .method = HTTP_GET, .handler = index_handler, .user_ctx = nullptr},
      {.uri = "/status", .method = HTTP_GET, .handler = status_handler, .user_ctx = nullptr},
      {.uri = "/capture", .method = HTTP_GET, .handler = capture_handler, .user_ctx = nullptr},
  };
  static const httpd_uri_t stream[] = {
      {.uri = "/stream", .method = HTTP_GET, .handler = stream_handler, .user_ctx = nullptr},
  };
  bool ok = start(&s_http, CAM_HTTP_PORT, 32768, 4, api, 3);
  ok = start(&s_stream, CAM_STREAM_PORT, 32769, CAM_MAX_STREAM_CLIENTS + 2, stream, 1) && ok;
  return ok;
}

int http_stream_clients() { return s_clients.load(); }
