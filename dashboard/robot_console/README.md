# PC 로봇 조종·모니터링 화면 (`robot_console`)

PC(Windows) 브라우저에서 **비전 모듈 Wi-Fi**를 통해 로봇 한 대를 직접 조종하고 카메라 영상을 보는 시험·조종 도구입니다.
Supabase·Pi 5를 거치는 관리자 대시보드(`dashboard/app`, `dashboard/web`)와는 별개입니다.

```text
브라우저 화면(index.html) ⇄ PC 중계(server.py) ⇄ UDP(docs/protocol.md) ⇄ 로봇 메인 보드(robot/)
                          ⇠ 카메라 영상(MJPEG) ⇠ 비전 모듈
```

브라우저는 UDP를 보낼 수 없어 `server.py`가 중간에서 통신 규약대로 명령을 보냅니다. 화면은 이 PC(`127.0.0.1`)에서만 열립니다.

## 화면

| 왼쪽 | 오른쪽 |
| --- | --- |
| 카메라 영상, 이동(전진·후진·좌·우·정지), 보폭·회전, 비상 정지, 잠금 해제, 일어서기, 로봇 상태 | LiDAR 스캔 화면(준비 중) |

- 이동은 **누르고 있는 동안만**(0.1초마다 다시 보냄, 0.3초 안에 안 오면 정지). 키보드 W/A/S/D·화살표, Space 정지, Esc 비상 정지.
- 기본값은 실물에서 시험한 값입니다: 보폭 20, 좌·우는 **전진하면서** ±5 회전(`move(20, 5)` / `move(20, -5)`).
- 안전 동작은 `host/robot_link.py`를 그대로 씁니다. 로봇은 켜지면 잠겨 있고, 사람이 **잠금 해제**해야 움직입니다.
  통신이 끊기면 로봇이 스스로 멈추고 잠깁니다. 배터리가 낮거나 모르면 이동 명령을 보내지 않습니다.
- **일어서기**는 잠금 해제 뒤에만 `CMD|POSE|<id>|<seq>|default|$`(= `set_default_pose()`)를 한 번 보냅니다.
  로봇 프로그램은 켜질 때 일어서지 않습니다(부팅 잠금).

## 준비

### 1. 비전 모듈: 제조사 기본 영상 펌웨어
비전 모듈이 Wi-Fi `HW_ESP32S3CAM`(개방형, 2.4GHz)을 띄우고 `192.168.5.1`이 됩니다.
맞춤 펌웨어(`firmware/vision_cam`)는 공유기 접속 방식이라 이 도구의 기본 구성과 다릅니다.
펌웨어 굽기·복구는 사용자가 [비전 모듈 펌웨어 문서](../../docs/vision-cam-firmware.md) 5절대로 합니다.

- 영상: `http://192.168.5.1:81/stream`, 상태: `http://192.168.5.1/status`
- 영상은 **한 화면에만** 나옵니다(두 번째 접속은 대기). 조종 화면은 한 탭에서만 엽니다.
- 비밀번호가 없는 Wi-Fi라 근처 누구나 영상을 볼 수 있습니다. 시험할 때만 켭니다.

### 2. 로봇 메인 보드: Python Editor로 파일 올리기 (사용자)
```powershell
python dashboard/robot_console/make_robot_files.py B
```
`build/robot_files_B/`에 11개 파일이 생깁니다(주석 없는 ASCII, 동작 코드는 `robot/`과 같음).
한 파일로 묶은 `build/robot_B/main.py`(약 49KB)는 편집기 전송이 `Download fail`로 실패해 나눠 올립니다.

1. 로봇을 받침대에 올리고 Python Editor로 메인 보드에 연결, Ctrl+C로 멈춤. 기존 `main.py` 복구 수단 확인([업로드·복구](../../docs/robot-upload.md)).
2. `robot/secrets.example.py`를 참고해 `secrets.py`를 만들어 올림: `WIFI_SSID = "HW_ESP32S3CAM"`, `WIFI_PASSWORD = ""`. **커밋하지 않음.**
3. `netutil` → `motion` → `roles` → `config` → `proto` → `vision` → `comm` → `lidar_bridge` → `core` → `app` 순서로 올리고 REPL에서 `import app` 확인.
4. 마지막에 `main.py`. 실행: REPL에서 `import main` 또는 다시 켜기.

### 3. PC
PC Wi-Fi를 `HW_ESP32S3CAM`에 연결합니다. 인터넷이 끊기므로 필요하면 유선 랜이나 휴대폰 블루투스·USB 테더링으로 인터넷을 따로 받습니다.

```powershell
python dashboard/robot_console/server.py --robot B --robot-ip auto --allow-real --cam http://192.168.5.1:81/stream
```

브라우저에서 `http://127.0.0.1:8090`을 엽니다. 처음 실행 때 Windows 방화벽 창이 뜨면 개인 네트워크를 허용합니다.
`--robot-ip auto`는 같은 Wi-Fi에 방송으로 HELLO를 보내고 처음 답한 해당 ID 로봇의 IP로 고정합니다.
안 찾아지면 REPL에서 `network.WLAN(network.STA_IF).ifconfig()`로 IP를 보고 `--robot-ip 192.168.5.x`로 넣습니다.

## 로봇 없이 시험

```powershell
python dashboard/robot_console/fake_robot.py
python dashboard/robot_console/server.py
```

`fake_robot.py`는 실제 `robot/core.py`를 PC에서 돌리고 MechDog 호출은 화면에 찍기만 합니다.

## 실물 확인 결과 (로봇 B, 사용자 실행, 2026-11-21)

- 비전 모듈을 기본 영상 펌웨어로 되돌린 뒤 PC·로봇 모두 `HW_ESP32S3CAM`에 연결, 화면에서 상태·영상 수신 확인.
- 받침대·바닥에서 전진·후진·좌·우·정지 동작 확인(사용자 관찰).
- 걷는 중 배터리가 낮아져 로봇이 `low_battery`로 스스로 잠김(쉬는 상태 약 7.2V). 기준값은 아직 가정값입니다(`robot/config.py`).
- 기울기는 `imu_unknown`으로 나옵니다(본체 시작 코드의 IMU 생성 인자 차이, 이동과 무관).

미확인: Python Editor 연결 없이 전원만 켰을 때 자동 실행, 로봇 A, 두 대 동시 사용, `MOVE(50,500)` 요청의 의도(회전 허용 범위 -30~30).
