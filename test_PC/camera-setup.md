# ESP32-S3 비전 모듈을 Windows 노트북에 연결

먼저 로봇 한 대씩 카메라 영상이 열리는지 확인합니다. 본체의 UDP 상태, 카메라의 HTTP 영상, LiDAR TCP 스캔은 각각 확인한 뒤 같은 로봇 ID로 콘솔에 연결합니다.

## 기존 펌웨어로 한 대 연결

1. 로봇 앞쪽 ESP32-S3 비전 모듈의 기본 영상 Wi‑Fi `HW_ESP32S3CAM`에 Windows를 연결합니다. 시험 중 노트북이 다른 Wi‑Fi로 자동 전환되지 않도록 네트워크 이름을 확인합니다.
2. 브라우저에서 `http://192.168.5.1/`을 열어 영상이 나오는지 확인하고 그 탭을 닫습니다. 기본 펌웨어는 한 화면에서 영상을 소비하므로 미리보기 탭을 닫은 뒤 콘솔을 엽니다.
3. 본체도 같은 카메라 Wi‑Fi에 접속하는 기존 사용자 시험 구성이라면, 확인한 본체 IP를 지정합니다. 아래에서 `ROBOT_B_IP`는 노트북 CMD의 로컬 환경 변수입니다.

   ```cmd
   python -m test_PC.robot_console.server --robot B --robot-ip %ROBOT_B_IP% --allow-real --cam http://192.168.5.1:81/stream
   ```

4. `http://127.0.0.1:8090`에서 카메라 영상과 B의 상태를 확인합니다. 영상만 확인할 때는 `--robot-ip`와 `--allow-real`을 빼면 실제 본체에 명령을 보내지 않습니다. 기본 카메라 Wi‑Fi는 개방형이므로 시험 구역에서 필요한 동안만 사용합니다.

## 공통 Wi‑Fi로 두 카메라 연결

기존 맞춤 펌웨어는 카메라를 2.4 GHz 공유기 또는 로봇망 AP의 클라이언트로 연결합니다. 노트북과 본체 A·B, 카메라 A·B가 같은 네트워크에서 서로 접근해야 합니다. 같은 SSID의 게스트망이라도 장치 간 통신이 막힐 수 있으므로 IP 도달 여부로 확인합니다.

1. 사용자 작업으로 카메라 플래시를 백업하고, 카메라용 이미지와 COM 포트를 확인한 뒤 [백업·설치·복구 절차](../docs/vision-cam-firmware.md)를 따릅니다. 카메라와 LiDAR 어댑터, MechDog 본체의 COM 포트는 구분합니다. 장치 관리자 또는 CMD의 `pnputil /enum-devices /class Ports /connected`에서 연결하기 전후를 비교할 수 있습니다.
2. 카메라 설정 시리얼을 115200bps, Newline으로 열고 `set robot A` 또는 `set robot B`, `set ssid`, `set pass`, `reboot`를 사용합니다. 카메라 ID를 본체 ID에 맞추고 자격 정보는 장치에 입력합니다.
3. Windows 브라우저에서 카메라별 `http://mechdog-a-cam.local/status`, `http://mechdog-b-cam.local/status`를 확인합니다. `.local` 이름이 해석되지 않으면 시리얼 상태 줄의 IP를 사용합니다. 상태 응답의 로봇 ID와 카메라 초기화 상태를 확인하고, `/capture`에서 한 장, `:81/stream`에서 MJPEG를 확인합니다. 키가 설정된 카메라는 펌웨어 문서의 키 전달 방식을 사용합니다.
4. 조종 콘솔의 `--cam`에는 같은 로봇의 스트림 URL을, `--robot-ip`에는 **본체** IP를 지정합니다. J5 경로를 확인할 때는 `--lidar-tcp`에도 같은 본체 IP를 지정합니다. 두 카메라의 상태와 영상을 각각 확인한 뒤 [고장·정지 항목을 포함한 실물 통합 시험](robot_console/README.md#사용자-실물-통합-시험)을 진행합니다.

## 펌웨어 빌드 확인

프로젝트 기준 코어는 ESP32 Arduino 3.3.12입니다. Windows CMD에서 아래 명령으로 균형 프로필의 로컬 합본과 소스·설정 해시를 확인합니다. 산출물은 Git에서 제외되는 `build\vision_cam\latest\`에 생깁니다.

```cmd
python tools\build_vision_cam.py --profile balanced --release
python tools\build_vision_cam.py --verify-release
```

빌드와 파일 검증 뒤 카메라별 부팅, 공유망 연결, Windows 영상 표시를 사용자 장비에서 확인합니다. [Arduino CLI 설치](https://arduino.github.io/arduino-cli/latest/installation/) · [ESP32 보드 패키지 설치](https://docs.espressif.com/projects/arduino-esp32/en/latest/installing.html)
