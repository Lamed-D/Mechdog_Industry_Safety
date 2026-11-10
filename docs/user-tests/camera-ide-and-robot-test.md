# 실제품 시험: 카메라 Arduino IDE 업로드 → 로봇 A/B 동작

이 문서는 **실제 제품을 맡은 사람이 수행하는 시험 절차**다. PC 가짜 모듈 시험이나
컴파일 성공으로 실물 합격을 대신하지 않는다. 현재 맞춤 펌웨어와 본체 동작은 실제품 미검증이다.
순서는 **1단계 카메라 펌웨어 업로드·영상 확인 → 2단계 로봇 본체 동작 확인**이다.
각 로봇을 한 대씩 시험하고 A/B 결과를 따로 기록한다. 에이전트는 아래 업로드·구동을 실행하지 않는다.

## 1단계: 앞쪽 ESP32-S3 카메라 — Arduino IDE

### 준비·백업

- [ ] 대상 A/B와 **카메라 COM 포트**를 확인한다. 본체 ESP32 포트를 선택하지 않는다.
- [ ] [카메라 설치 4.1~4.2절](../vision-cam-firmware.md#41-준비)을 따라 기존 카메라 플래시 전체를 먼저 백업한다.
  본체 코드 백업은 사용자 보고로 완료됐지만 **카메라 플래시 백업과는 별개**다. 기존 백업이 있으면 대상과 복구 가능 여부를 확인한다.
- [ ] 본체 전원을 끄고 카메라 IIC 케이블을 분리한 뒤 데이터 USB로 카메라만 PC에 연결한다.
  이는 역급전 여부 미확인에 따른 우리 안전 권고이며 제조사 확정 절차로 주장하지 않는다.
- [ ] 포트를 점유한 Python Editor·다른 시리얼 프로그램을 닫는다.

### IDE 설치·소스 열기

1. Arduino IDE 2.x를 열고 파일 → 환경 설정 → 추가 보드 관리자 URL에 다음 공식 주소를 넣는다.
   `https://espressif.github.io/arduino-esp32/package_esp32_index.json`
2. 보드 매니저에서 **esp32 by Espressif Systems 3.3.12**를 선택해 설치한다.
   이미 해당 버전이면 바꾸지 않는다. 다른 버전의 컴파일·실행은 검증하지 않았다.
3. 파일 → 열기에서 저장소의 **`firmware/vision_cam/vision_cam.ino`**를 연다.
   같은 폴더의 cpp/h 파일을 함께 유지한다. 빈 새 스케치에 ino 내용만 붙여 넣지 않는다.
4. 아래 도구 설정을 맞춘다. 카메라 핀은 소스에 정의돼 있으므로 보드 이름만 보고 다른 핀으로 바꾸지 않는다.

| IDE 항목 | 선택값 |
| --- | --- |
| Board | ESP32S3 Dev Module |
| Port | 카메라를 연결했을 때 나타난 CH340 COM 포트 |
| PSRAM | OPI PSRAM |
| Flash Mode | DIO 80MHz |
| Flash Size | 4MB (32Mb) |
| Partition Scheme | Huge APP (3MB No OTA/1MB SPIFFS) |
| CPU Frequency | 240MHz (WiFi) |
| USB CDC On Boot | Disabled |
| Erase All Flash Before Sketch Upload | Disabled |
| Upload Speed | 115200 — 이 절차의 보수적인 전송 설정. 실제 업로드는 미검증 |

값은 프로젝트의 CLI 빌드 설정과 설치된 코어 메뉴를 대조했다. 업로드 속도는 실행 중 영상 속도와 무관하다.
IDE 언어·버전에 따라 메뉴 표기가 다르면 [빌드 FQBN](../vision-cam-firmware.md#6-직접-빌드-개발자)과 대조한다.
그 밖의 메뉴는 기본값을 유지한다. 실물 플래시/PSRAM 사양이 다르다고 확인되면 업로드를 중단하고 기록한다.

### 컴파일·업로드·설정

1. **검증(체크 표시)**을 눌러 컴파일한다. 오류가 있으면 업로드하지 않고 오류 종류만 기록한다.
2. 백업·포트·설정을 다시 확인한 담당자가 **업로드(오른쪽 화살표)**를 누른다.
   IDE는 소스 스케치를 컴파일해 올린다. `mechdog_vision_cam_0x0.bin`을 스케치로 열거나 소스 업로드와 섞지 않는다.
3. 완료 후 시리얼 모니터를 **115200 baud / Newline**으로 열고 카메라 초기화와 I2C 상태를 확인한다.
   연결 실패 때 버튼 조합을 추측하지 말고 케이블·포트 점유·장치 인식을 먼저 확인한다.
4. [설정 4.4절](../vision-cam-firmware.md#44-3-wi-fi로봇-id-설정-usb-시리얼)대로
   `set robot A` 또는 `set robot B`, `set ssid <로봇망 SSID>`, `set pass <비밀번호>`, `show`, `reboot`를 실행한다.
   비밀번호는 장치에만 입력하고 저장소·시험 결과·채팅에 적지 않는다. secrets.h 작성은 필수가 아니다.
5. PC를 같은 로봇망에 연결하고 실제 카메라 IP로 다음을 확인한다.

| 실제품 확인 | 정상 관측 | A | B |
| --- | --- | --- | --- |
| `http://<카메라 IP>/status` | robot ID 일치, camera.ok=true, STA 접속 | 미실행 | 미실행 |
| `http://<카메라 IP>/capture` | 현재 장면 한 장, 깨짐 없음 | 미실행 | 미실행 |
| `http://<카메라 IP>:81/stream` | 실제 영상 갱신, 움직이는 물체에 따라 변경 | 미실행 | 미실행 |
| 수신창 닫고 다시 열기 | 새 영상 수신, 이전 영상에 고정되지 않음 | 미실행 | 미실행 |
| [화질·지연 기록](../vision-quality.md) | fps·프레임 나이·끊김을 수치로 기록 | 미실행 | 미실행 |

접근 키를 설정했다면 안내대로 요청에 키가 필요하다. 키가 든 주소·사람 영상·사진을 결과에 붙이지 않는다.
실제 Pi 5 비전 모델의 정확도와 처리량은 이 PC 확인으로 합격 처리하지 않는다.
실패하면 2단계로 넘어가지 않고 [복구 5절](../vision-cam-firmware.md#5-복구)대로
백업 또는 기본 영상 전송 펌웨어로 복구한다. 복구 후에도 영상 확인 결과를 기록한다.

## 2단계: 실제 로봇 본체 A/B — Hiwonder Python Editor

**본체는 순정 MicroPython과 공식 Python API를 유지한다.** 본체에 카메라 Arduino 스케치를 올리지 않는다.
예비 `firmware/main_arduino/`는 실제품 시험용 업로드 대상이 아니다.

1. 카메라 USB를 제거하고 본체 전원을 끈 상태에서 원래 IIC 케이블을 복원한다.
2. [본체 시험 인계서](robot-python-handoff.md)대로 PC에서 시험 전달 폴더를 만들고 시험 py만 Download한다.
   통합 main.py를 먼저 덮어쓰지 않는다. 기존 자동 실행 중지와 본체 백업 복구 위치를 확인한다.
3. [본체 동작 체크리스트](robot-python-checklist.md)의 API/배터리·IMU 읽기 → 루프 → 카메라 I2C → 정지를 확인한다.
4. 사용자가 지정한 시험 범위에서 `robot_motion_check.py`로 짧은 동작을 **한 항목씩** 확인한다.
   지지 상태·빈 시험 공간·전원 차단 수단을 준비하고 손으로 다리를 붙들지 않는다.
5. 실제 자세·이동·정지와 예외 복구를 눈으로 확인하고 [결과 양식](results-template.md)에 A/B별로 기록한다.
   출력 `calls_completed`만으로 합격 처리하지 않는다. 이상 동작·정지 실패 시 즉시 시험을 중단한다.
6. 담당자의 실제 결과를 검토한 뒤 통합 main 적용 여부를 정한다. 실패 시 기존 본체 백업으로 복구한다.

공식 설정 근거: [ESP32 IDE 설치](https://docs.espressif.com/projects/arduino-esp32/en/latest/installing.html),
[IDE 도구 메뉴](https://docs.espressif.com/projects/arduino-esp32/en/latest/guides/tools_menu.html).
