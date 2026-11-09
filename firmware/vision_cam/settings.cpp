#include "settings.h"

#include <Arduino.h>
#include <Preferences.h>

#include "config.h"

// NVS 이름공간과 키. 값은 카메라 모듈 플래시의 NVS 영역에만 저장됩니다.
#define NS "camcfg"

struct Field {
  const char *name;      // 시리얼 명령에서 쓰는 이름
  const char *fallback;  // secrets.h(없으면 예시) 값
  bool secret;           // show 에서 가릴지
  char value[72];
};

static Field s_fields[] = {
    {"robot", CAM_ROBOT_ID, false, ""},
    {"ssid", CAM_WIFI_SSID, false, ""},
    {"pass", CAM_WIFI_PASSWORD, true, ""},
    {"ap_pass", CAM_AP_PASSWORD, true, ""},
    {"key", CAM_ACCESS_KEY, true, ""},
};
enum { F_ROBOT, F_SSID, F_PASS, F_AP_PASS, F_KEY, F_COUNT };

static char s_line[160];
static size_t s_len = 0;

static Field *find(const char *name) {
  for (int i = 0; i < F_COUNT; i++)
    if (strcmp(s_fields[i].name, name) == 0) return &s_fields[i];
  return nullptr;
}

static void load() {
  Preferences p;
  bool opened = p.begin(NS, true);
  for (int i = 0; i < F_COUNT; i++) {
    Field &f = s_fields[i];
    // 저장된 값이 있으면(빈 문자열 포함) 그것을 씁니다. clear 로 지워야 secrets.h 값으로 돌아갑니다.
    bool has = opened && p.isKey(f.name);
    String stored = has ? p.getString(f.name, "") : String();
    const char *src = has ? stored.c_str() : f.fallback;
    strncpy(f.value, src, sizeof(f.value) - 1);
    f.value[sizeof(f.value) - 1] = '\0';
  }
  if (opened) p.end();
  // 로봇 ID 는 A 또는 B 만 받습니다. 그 밖이면 A 로 두고 알립니다.
  if (strcmp(s_fields[F_ROBOT].value, "A") != 0 && strcmp(s_fields[F_ROBOT].value, "B") != 0) {
    Serial.printf("[cfg] robot '%s' 는 쓸 수 없어 A 로 둡니다\n", s_fields[F_ROBOT].value);
    strcpy(s_fields[F_ROBOT].value, "A");
  }
}

static void show() {
  for (int i = 0; i < F_COUNT; i++) {
    const Field &f = s_fields[i];
    if (f.secret) {
      Serial.printf("  %-8s %s\n", f.name, f.value[0] ? "(설정됨, 길이 숨김)" : "(비어 있음)");
    } else {
      Serial.printf("  %-8s %s\n", f.name, f.value[0] ? f.value : "(비어 있음)");
    }
  }
}

static void help() {
  Serial.println("[cfg] 명령 (줄 끝 Enter, 115200bps):");
  Serial.println("  show                    현재 설정 보기(비밀값은 가림)");
  Serial.println("  set robot A|B           로봇 ID");
  Serial.println("  set ssid <이름>         공유기 SSID(공백 포함 가능)");
  Serial.println("  set pass <비밀번호>     공유기 비밀번호");
  Serial.println("  set ap_pass <8자 이상>  점검용 AP 비밀번호(set ap_pass 만 쓰면 AP 끔)");
  Serial.println("  set key <값>            HTTP 접근 키, 영문·숫자 . _ ~ - (set key 만 쓰면 키 없음)");
  Serial.println("  clear <이름>            저장값 지우기(빌드 때 secrets.h 값으로 돌아감)");
  Serial.println("  reboot                  다시 시작(설정은 재시작 뒤 적용)");
}

static void handle(char *line) {
  while (*line == ' ') line++;
  if (*line == '\0') return;
  if (strcmp(line, "help") == 0) return help();
  if (strcmp(line, "show") == 0) return show();
  if (strcmp(line, "reboot") == 0) {
    Serial.println("[cfg] 다시 시작합니다");
    delay(100);
    ESP.restart();
  }
  bool is_set = strncmp(line, "set ", 4) == 0;
  bool is_clear = strncmp(line, "clear ", 6) == 0;
  if (!is_set && !is_clear) {
    Serial.println("[cfg] 모르는 명령입니다. help 를 입력하세요");
    return;
  }
  char *name = line + (is_set ? 4 : 6);
  while (*name == ' ') name++;
  char *value = strchr(name, ' ');
  if (value) {
    *value++ = '\0';
  } else {
    value = (char *)"";
  }
  Field *f = find(name);
  if (f == nullptr) {
    Serial.printf("[cfg] 모르는 이름 '%s'\n", name);
    return;
  }
  if (is_set) {
    if (strlen(value) >= sizeof(f->value)) return (void)Serial.println("[cfg] 값이 너무 깁니다");
    if (f == &s_fields[F_ROBOT] && strcmp(value, "A") != 0 && strcmp(value, "B") != 0)
      return (void)Serial.println("[cfg] robot 은 A 또는 B 만 됩니다");
    if (f == &s_fields[F_AP_PASS] && value[0] && strlen(value) < 8)
      return (void)Serial.println("[cfg] ap_pass 는 8자 이상이어야 합니다");
    if (f == &s_fields[F_KEY]) {  // 주소창에 그대로 쓸 수 있는 문자만(인코딩 차이로 늘 거부되는 일 방지)
      for (const char *c = value; *c; c++)
        if (!isalnum((unsigned char)*c) && !strchr("._~-", *c))
          return (void)Serial.println("[cfg] key 는 영문·숫자와 . _ ~ - 만 됩니다");
    }
  }
  Preferences p;
  if (!p.begin(NS, false)) return (void)Serial.println("[cfg] 저장 공간을 열 수 없습니다");
  bool ok = is_set ? p.putString(f->name, value) == strlen(value) || value[0] == '\0' : p.remove(f->name);
  p.end();
  Serial.printf("[cfg] %s %s %s. reboot 하면 적용됩니다\n", f->name, is_set ? "저장" : "지움",
                ok ? "완료" : "실패");
}

void settings_begin() {
  load();
  Serial.println("[cfg] 설정 명령은 help");
  show();
}

void settings_poll_serial() {
  while (Serial.available()) {
    int c = Serial.read();
    if (c == '\r' || c == '\n') {
      if (s_len > 0) {
        s_line[s_len] = '\0';
        handle(s_line);
        s_len = 0;
      }
    } else if (s_len < sizeof(s_line) - 1) {
      s_line[s_len++] = (char)c;
    }
  }
}

const char *settings_robot() { return s_fields[F_ROBOT].value; }
const char *settings_ssid() { return s_fields[F_SSID].value; }
const char *settings_password() { return s_fields[F_PASS].value; }
const char *settings_ap_password() { return s_fields[F_AP_PASS].value; }
const char *settings_key() { return s_fields[F_KEY].value; }
