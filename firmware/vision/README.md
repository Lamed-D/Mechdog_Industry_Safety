# 비전 모듈 맞춤 펌웨어 (`vision`)

로봇 앞쪽 ESP32-S3 카메라용입니다. **MechDog 메인 보드에 올리지 않습니다.**
각 카메라는 공통 로봇 Wi-Fi에서 담당 Windows 노트북에 영상을 제공합니다. [Windows 카메라 연결 안내](../../ai/dashboard.md)를 참조하세요.
아래 빌드 명령으로 현재 소스의 합본을 만듭니다. 이전 배포 이미지는 제거했고 산출물은 build에만 둡니다.

자세한 설치·설정·복구·빌드: [ai/firmware.md](../../ai/firmware.md) 6절

저장소 루트에서 `python firmware/build.py <ID> --only vision` 을 먼저 실행합니다(로봇 ID가 기본값으로 들어간 합본).

## 설치 (AI 에이전트가 수행)

AI 에이전트가 아래를 직접 합니다. 사람은 **1번 케이블·전원 조작**과 끝난 뒤 IIC 케이블 복원만 하면 됩니다.

로봇마다 다른 것은 **로봇 ID(A/B)** 하나뿐입니다. 카메라의 ID는 **그 카메라가 달린 로봇의 ID**를 씁니다.
아래 `<ID>`(대문자 A/B)를 그 값으로 바꿔 씁니다. 두 로봇의 카메라가 같은 ID를 쓰지 않게 합니다.

1. 본체 전원을 끄고 카메라만 USB 데이터 케이블로 PC에 연결, 카메라 COM 포트를 확인합니다.
   (본체 전원 끄기는 공식 절차가 아닌 우리 안전 권고: USB·본체 전원 동시 공급을 피하기 위함)
2. **굽기** (백업 없이 바로):
   - 이미 맞춤 펌웨어가 있는 카메라(시리얼 `show` 에 robot·ssid 가 보임): 앱만 굽습니다. ID·Wi-Fi 설정이 그대로 남아 3번이 필요 없습니다.
     `esptool --chip esp32s3 --port COMx --baud 460800 write-flash 0x10000 build/robot_<ID>/vision/compile/vision.ino.bin`
   - 처음 굽는 카메라: 합본을 주소 **0x0** 에
     `esptool --chip esp32s3 --port COMx --baud 460800 write-flash 0x0 build/robot_<ID>/vision/latest/mechdog_vision_cam_0x0.bin`
     (제조사 플래시 도구: ESP32-S3 / 0x0000 / 80MHz / DIO / 460800, ERASE 누르지 않음)
3. **Wi-Fi 설정** (처음 굽거나 핫스팟 이름·비밀번호가 바뀐 경우만): 시리얼 115200bps, 줄 끝 Newline 으로 연 뒤
   ```text
   set robot <ID>
   set ssid <공유기 SSID>
   set pass <공유기 비밀번호>
   reboot
   ```
   Wi-Fi 비밀번호는 에이전트가 Windows에서 얻어 시리얼로만 입력하고 어디에도 남기지 않습니다.
   점검용 AP(`MECHDOG-<ID>-CAM`, STA 실패 30초 뒤)의 기본 비밀번호는 `password` 입니다(`set ap_pass` 로 변경).
4. **확인**: 같은 공유기에 붙은 PC에서 아래 주소를 엽니다. 이름은 로봇 ID를 따라 바뀝니다.

   | 로봇 ID | 상태 | 영상 |
   | --- | --- | --- |
   | A | `http://mechdog-a-cam.local/status` | `http://mechdog-a-cam.local:81/stream` |
   | B | `http://mechdog-b-cam.local/status` | `http://mechdog-b-cam.local:81/stream` |

   `.local` 이름이 안 열리면(Windows·휴대폰은 mDNS가 안 될 수 있음) 재시작 뒤 시리얼 상태 줄의 `sta <IP>` 로
   `http://<IP>/status`, `http://<IP>:81/stream` 을 엽니다. 접근 키를 설정했으면 주소 끝에 `?key=<키>` 를 붙입니다.
5. 다른 로봇의 카메라는 그 로봇의 ID로 같은 과정을 반복합니다. 문제가 있으면 합본을 0x0 에 다시 굽고 3번 설정을 합니다.

## 주소

| 주소 | 내용 |
| --- | --- |
| `:81/stream` | MJPEG, 최신 프레임만, 최대 2 수신자 |
| `:80/capture` | JPEG 한 장 |
| `:80/status` | JSON 상태 |

## 직접 빌드

`python firmware/build.py <ID> --only vision` (로봇 전용 합본). 공통 합본·검사는 `python firmware/builder/build_vision_cam.py [--release] [--verify-release] [--robot <ID>]` (`secrets.h` 있으면 합본 생성 멈춤).

로봇 B 카메라에서 실물 동작 확인(v0.1.8). v0.1.9는 AP 기본 비밀번호만 바뀌었고 실물 미검증입니다. 로봇 A 카메라·장시간 동작은 실물 미검증입니다.
