#include "net.h"

#include <Arduino.h>
#include <ESPmDNS.h>
#include <WiFi.h>
#include <ctype.h>

#include "config.h"
#include "settings.h"

static char s_host[24];
static char s_ap_ssid[24];
static bool s_ap_on = false;
static bool s_mdns = false;
static bool s_sta_was_up = false;
static uint32_t s_sta_down_since = 0;  // STA 가 끊긴(또는 부팅한) 시각
static uint32_t s_last_try = 0;
static uint32_t s_net_ok_ms = 0;       // 마지막으로 네트워크가 쓸 만했던 시각
static uint32_t s_reconnects = 0;

static bool ssid_set() { return settings_ssid()[0] != '\0'; }
static bool ap_allowed() { return strlen(settings_ap_password()) >= 8; }

static void apply_static_ip() {
  if (CAM_STATIC_IP[0] == '\0') return;
  IPAddress ip, gw, mask;
  if (ip.fromString(CAM_STATIC_IP) && gw.fromString(CAM_STATIC_GATEWAY) && mask.fromString(CAM_STATIC_NETMASK)) {
    WiFi.config(ip, gw, mask, gw);
  }
}

static void start_sta() {
  if (!ssid_set()) return;
  WiFi.begin(settings_ssid(), settings_password());
}

void net_begin() {
  char id[4] = {0};
  for (int i = 0; i < 3 && settings_robot()[i]; i++) id[i] = (char)tolower((unsigned char)settings_robot()[i]);
  snprintf(s_host, sizeof(s_host), "mechdog-%s-cam", id);
  snprintf(s_ap_ssid, sizeof(s_ap_ssid), "MECHDOG-%s-CAM", settings_robot());

  WiFi.persistent(false);  // 자격 정보를 플래시에 따로 저장하지 않음
  WiFi.setHostname(s_host);
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);  // 절전 끄기: 스트림 지연·끊김 방지
  WiFi.setAutoReconnect(false);  // 재접속은 net_loop 가 맡음(두 곳에서 다시 붙지 않게)
  apply_static_ip();
  start_sta();
  uint32_t now = millis();
  s_sta_down_since = now;
  s_last_try = now;
  s_net_ok_ms = now;
}

void net_loop() {
  uint32_t now = millis();
  bool sta = WiFi.status() == WL_CONNECTED;

  if (sta) {
    if (!s_sta_was_up) {
      s_sta_was_up = true;
      WiFi.setSleep(false);
    }
    if (s_ap_on) {  // 공유기에 붙었으면 점검용 AP는 끕니다.
      WiFi.softAPdisconnect(true);
      WiFi.mode(WIFI_STA);
      WiFi.setSleep(false);
      s_ap_on = false;
    }
  } else {
    if (s_sta_was_up) {
      s_sta_was_up = false;
      s_sta_down_since = now;
    }
    // 점검용 AP에 누가 붙어 있으면 STA 재시도(채널 탐색)를 드물게 해 AP 연결이 끊기지 않게 합니다.
    uint32_t retry_ms = (s_ap_on && WiFi.softAPgetStationNum() > 0) ? CAM_STA_RETRY_AP_BUSY_MS : CAM_STA_RETRY_MS;
    if (ssid_set() && now - s_last_try >= retry_ms) {
      s_last_try = now;
      s_reconnects++;
      WiFi.disconnect(false, false);
      start_sta();
    }
    if (!s_ap_on && ap_allowed() && (!ssid_set() || now - s_sta_down_since >= CAM_STA_FALLBACK_MS)) {
      WiFi.mode(WIFI_AP_STA);
      // 제조사 기본 펌웨어와 같은 주소(192.168.5.1)를 써서 점검 때 헷갈리지 않게 합니다.
      WiFi.softAPConfig(IPAddress(192, 168, 5, 1), IPAddress(192, 168, 5, 1), IPAddress(255, 255, 255, 0));
      WiFi.softAP(s_ap_ssid, settings_ap_password());
      WiFi.setSleep(false);
      s_ap_on = true;
    }
  }

  if (!s_mdns && (sta || s_ap_on)) {
    if (MDNS.begin(s_host)) {
      MDNS.addService("http", "tcp", CAM_HTTP_PORT);
      MDNS.addServiceTxt("http", "tcp", "robot", settings_robot());
      MDNS.addServiceTxt("http", "tcp", "stream_port", String(CAM_STREAM_PORT));
      s_mdns = true;
    }
  }

  bool usable = sta || (s_ap_on && WiFi.softAPgetStationNum() > 0);
  if (usable || !ssid_set()) {
    s_net_ok_ms = now;
  } else if (now - s_net_ok_ms > CAM_NET_RESTART_MS) {
    ESP.restart();  // 오래 고립되면 Wi-Fi 상태를 처음부터 다시 만듭니다.
  }
}

bool net_sta_connected() { return WiFi.status() == WL_CONNECTED; }
bool net_ap_on() { return s_ap_on; }
int net_rssi() { return net_sta_connected() ? WiFi.RSSI() : 0; }
const char *net_hostname() { return s_host; }
uint32_t net_sta_reconnects() { return s_reconnects; }

const char *net_mode() {
  bool sta = net_sta_connected();
  if (sta && s_ap_on) return "sta+ap";
  if (sta) return "sta";
  if (s_ap_on) return "ap";
  return "none";
}

void net_ip(char *out, int cap) {
  IPAddress ip = net_sta_connected() ? WiFi.localIP() : (s_ap_on ? WiFi.softAPIP() : IPAddress());
  snprintf(out, cap, "%u.%u.%u.%u", ip[0], ip[1], ip[2], ip[3]);
}
