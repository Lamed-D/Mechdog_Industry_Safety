# PC 로봇 조종·모니터링 화면 (`robot_console`)

PC(Windows) 브라우저에서 **비전 모듈 Wi-Fi**를 통해 로봇 한 대를 직접 조종하고 카메라 영상을 보는 시험·조종 도구입니다.
상태·카메라·LiDAR를 한 화면에서 점검합니다. 두 대의 낙상 알림·안내 시나리오는 [상위 시험 안내](../README.md)를 따릅니다.
기본 카메라 AP와 두 대 공통 Wi‑Fi 연결은 [ESP32-S3 카메라 연결 안내](../camera-setup.md)에 있습니다.

```text
브라우저 화면(index.html) ⇄ PC 중계(server.py) ⇄ UDP(docs/protocol.md) ⇄ 로봇 메인 보드(robot/)
                          ⇠ 카메라 영상(MJPEG) ⇠ 비전 모듈
```

브라우저는 UDP를 보낼 수 없어 `server.py`가 중간에서 통신 규약대로 명령을 보냅니다. 화면은 이 PC(`127.0.0.1`)에서만 열립니다.

## 화면

- 카메라 영상, 이동, 비상 정지, 잠금 해제, 일어서기와 로봇 상태를 표시합니다.
- LiDAR는 USB 또는 TCP에서 최신 한 회전을 거리 점으로 그립니다. 빈 각도와 무효 측정은 비워 두고, 1초 동안 새 스캔이 없거나 연결이 끊기면 점을 지웁니다. 센서 원시 각도를 표시하므로 로봇의 정면과 일치하는지는 장착 후 확인합니다.

- 이동은 **누르고 있는 동안만**(0.1초마다 다시 보냄, 0.3초 안에 안 오면 정지). 키보드 W/A/S/D·화살표, Space 정지, Esc 비상 정지.
- 기본값은 실물에서 시험한 값입니다: 보폭 20, 좌·우는 **전진하면서** ±5 회전(`move(20, 5)` / `move(20, -5)`).
- 안전 동작은 `host/robot_link.py`를 그대로 씁니다. 로봇은 켜지면 잠겨 있고, 사람이 **잠금 해제**해야 움직입니다.
  통신이 끊기면 로봇이 스스로 멈추고 잠깁니다. 배터리가 낮거나 모르면 이동 명령을 보내지 않습니다.
- **일어서기**는 잠금 해제 뒤에만 `CMD|POSE|<id>|<seq>|default|$`(= `set_default_pose()`)를 한 번 보냅니다.
  배터리와 대기 상태가 확인돼야 하며, 정지·비상 정지·종료가 대기 요청을 취소합니다.

## 준비

### 1. 비전 모듈: 제조사 기본 영상 펌웨어
비전 모듈이 Wi-Fi `HW_ESP32S3CAM`(개방형, 2.4GHz)을 띄우고 `192.168.5.1`이 됩니다.
맞춤 펌웨어(`firmware/vision_cam`)는 공유기 접속 방식이라 이 도구의 기본 구성과 다릅니다.
펌웨어 굽기·복구는 사용자가 [비전 모듈 펌웨어 문서](../../docs/vision-cam-firmware.md) 5절대로 합니다.

- 영상: `http://192.168.5.1:81/stream`, 상태: `http://192.168.5.1/status`
- 영상은 **한 화면에만** 나옵니다(두 번째 접속은 대기). 조종 화면은 한 탭에서만 엽니다.
- 비밀번호가 없는 Wi-Fi라 근처 누구나 영상을 볼 수 있습니다. 시험할 때만 켭니다.

### 2. 로봇 메인 보드: 펌웨어 올리기 (사용자)

로봇 메인 보드 펌웨어는 두 가지입니다. 콘솔은 **같은 통신 규약**([docs/protocol.md](../../docs/protocol.md))을 쓰므로 어느 쪽이든 그대로 조종됩니다.

- **Arduino 판(기본):** [firmware/main_arduino](../../firmware/main_arduino/README.md) 를 Arduino IDE 로 올립니다. 핫스팟·세팅은 [로봇 Arduino 펌웨어 세팅 가이드](../../docs/robot-arduino-setup.md).
- **MicroPython 판(되돌림·비교용):** 아래 Python Editor 방식.

```powershell
python -m test_PC.robot_console.make_robot_files B
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
python -m test_PC.robot_console.server --robot B --robot-ip auto --allow-real --cam http://192.168.5.1:81/stream
```

브라우저에서 `http://127.0.0.1:8090`을 엽니다. 처음 실행 때 Windows 방화벽 창이 뜨면 개인 네트워크를 허용합니다.
`--robot-ip auto`는 같은 Wi-Fi에 방송으로 HELLO를 보내고 처음 답한 해당 ID 로봇의 IP로 고정합니다.
안 찾아지면 REPL에서 `network.WLAN(network.STA_IF).ifconfig()`로 IP를 보고 `--robot-ip 192.168.5.x`로 넣습니다.

## 로봇 없이 통합 시험

```cmd
test_PC\run.cmd console
```

각자 담당 ID로 실행합니다. 한 명령이 가짜 본체·합성 카메라·LiDAR·콘솔을 시작합니다.

```cmd
python -m test_PC.mock_station --robot B
```

브라우저에서 `http://127.0.0.1:8090`을 엽니다. B와 부팅 잠금, 합성 영상, 정사각형 LiDAR 점이 표시되는지 확인합니다. 가짜 본체의 잠금을 해제하고 이동을 눌렀다 놓아 가짜 MechDog 콘솔 로그에 이동과 정지가 찍히는지 확인합니다. 비상 정지 후 잠금 상태를 확인합니다. CMD에서 Ctrl+C를 누르면 모의 프로세스가 함께 종료됩니다. 개별 장치 단절은 `test_PC\run.cmd console`로도 확인합니다.

## 사용자 실물 통합 시험

1. USB 직결만 확인할 때는 [상위 안내](../README.md)대로 `pyserial`을 설치한 환경에서 아래 명령을 실행합니다. 확인한 어댑터 포트를 사용하고 USB 진단과 콘솔을 동시에 열지 않습니다.

   ```cmd
   .private\lidar-pc\Scripts\python.exe -m test_PC.robot_console.server --lidar-usb COM번호
   ```

2. J5 UART·Wi-Fi 경로는 로봇 주소와 같은 로봇의 카메라 URL을 확인한 뒤 아래 명령을 실행합니다. `%ROBOT_B_IP%`와 `%CAM_B_URL%`은 해당 시험 환경의 값입니다. 카메라 기본 AP 시험에서 TCP 20108을 쓸 수 없으면 우선 USB 직결 화면과 본체 상태를 개별 확인합니다.

   ```cmd
   python -m test_PC.robot_console.server --robot B --robot-ip %ROBOT_B_IP% --allow-real --cam %CAM_B_URL% --relay-lidar
   ```

3. 잠긴 상태에서 본체 ID, 카메라, LiDAR 점을 확인합니다. 사용자 승인 범위에서 로봇을 받침대에 두고 잠금 해제, 정지와 비상 정지부터 시험합니다. Wi-Fi를 끊었을 때 명령 watchdog으로 본체가 정지·래치하는지, LiDAR 점이 지워지는지 확인합니다. 콘솔 종료 후 정지 상태를 확인합니다. A도 주소·카메라·로봇 ID를 바꿔 같은 절차를 반복합니다.

운영자마다 자기 노트북과 콘솔에서 자기 본체 하나만 연결합니다. 기존 두 본체용 정지형 진단 어댑터를 별도로 시험하려면 두 담당 콘솔을 모두 종료하고 장비 확인 범위에서 진행합니다. 각 콘솔에서 LiDAR TCP를 쓸 때는 같은 장치에 별도 진단이나 ROS 노드를 연결하지 않습니다.

## 실물 확인 결과 (로봇 B, 사용자 실행, 2026-11-21)

- 비전 모듈을 기본 영상 펌웨어로 되돌린 뒤 PC·로봇 모두 `HW_ESP32S3CAM`에 연결, 화면에서 상태·영상 수신 확인.
- 받침대·바닥에서 전진·후진·좌·우·정지 동작 확인(사용자 관찰).
- 걷는 중 배터리가 낮아져 로봇이 `low_battery`로 스스로 잠김(쉬는 상태 약 7.2V). 기준값은 아직 가정값입니다(`robot/config.py`).
- 기울기는 `imu_unknown`으로 나옵니다(본체 시작 코드의 IMU 생성 인자 차이, 이동과 무관).

미확인: Python Editor 연결 없이 전원만 켰을 때 자동 실행, 로봇 A, 두 대 동시 사용, `MOVE(50,500)` 요청의 의도(회전 허용 범위 -30~30).
