# 비전 모듈 맞춤 펌웨어 (`vision_cam`)

로봇 앞쪽 ESP32-S3 카메라용입니다. **MechDog 메인 보드에 올리지 않습니다.**
카메라 영상을 전용 공유기 Wi-Fi로 Pi 5에 보냅니다. 인식은 Pi 5가 합니다.
현재 소스 v0.1.3은 아래 명령으로 최신 합본을 만듭니다. 이전 배포 이미지는 제거했고 산출물은 build에만 둡니다.

자세한 설치·설정·복구·빌드: [docs/vision-cam-firmware.md](../../docs/vision-cam-firmware.md)

저장소 루트에서 `python tools/build_vision_cam.py --release`를 먼저 실행합니다.

## 빠른 설치 (사용자)

로봇마다 다른 것은 **로봇 ID(A/B)** 하나뿐입니다. 카메라의 ID는 **그 카메라가 달린 로봇의 ID**를 씁니다.
아래 `<ID>`(대문자 A/B)를 그 값으로 바꿔 씁니다. 두 로봇의 카메라가 같은 ID를 쓰지 않게 합니다.

1. 본체 전원을 끄고 카메라만 USB 데이터 케이블로 PC에 연결, 카메라 COM 포트를 확인합니다.
   (본체 전원 끄기는 공식 절차가 아닌 우리 안전 권고: USB·본체 전원 동시 공급을 피하기 위함)
2. **현재 플래시 백업** (저장소 밖에 보관):
   `esptool --chip esp32s3 --port COMx --baud 460800 read-flash 0 ALL C:\camera-backup\robot<ID>_cam_full.bin`
3. **굽기**: `build/vision_cam/latest/mechdog_vision_cam_0x0.bin` 을 주소 **0x0** 에
   `esptool --chip esp32s3 --port COMx --baud 460800 write-flash 0x0 build/vision_cam/latest/mechdog_vision_cam_0x0.bin`
   (제조사 플래시 도구: ESP32-S3 / 0x0000 / 80MHz / DIO / 460800, ERASE 누르지 않음)
4. **Wi-Fi 설정**: 시리얼 115200bps, 줄 끝 Newline 으로 연 뒤
   ```text
   set robot <ID>
   set ssid <공유기 SSID>
   set pass <공유기 비밀번호>
   reboot
   ```
5. **확인**: 같은 공유기에 붙은 PC에서 아래 주소를 엽니다. 이름은 로봇 ID를 따라 바뀝니다.

   | 로봇 ID | 상태 | 영상 |
   | --- | --- | --- |
   | A | `http://mechdog-a-cam.local/status` | `http://mechdog-a-cam.local:81/stream` |
   | B | `http://mechdog-b-cam.local/status` | `http://mechdog-b-cam.local:81/stream` |

   `.local` 이름이 안 열리면(Windows·휴대폰은 mDNS가 안 될 수 있음) 재시작 뒤 시리얼 상태 줄의 `sta <IP>` 로
   `http://<IP>/status`, `http://<IP>:81/stream` 을 엽니다. 접근 키를 설정했으면 주소 끝에 `?key=<키>` 를 붙입니다.
6. 다른 로봇의 카메라는 그 로봇의 ID로 같은 과정을 반복합니다. 문제가 있으면 2번 백업을 0x0 에 다시 굽습니다.

## 주소

| 주소 | 내용 |
| --- | --- |
| `:81/stream` | MJPEG, 최신 프레임만, 최대 2 수신자 |
| `:80/capture` | JPEG 한 장 |
| `:80/status` | JSON 상태 |

## 직접 빌드

`python tools/build_vision_cam.py` (컴파일만), `--release` (합본 bin 생성, `secrets.h` 있으면 멈춤).

실물 미검증입니다. 확인 결과는 이슈 #29 에 남깁니다.
