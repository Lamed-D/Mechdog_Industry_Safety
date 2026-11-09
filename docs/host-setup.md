# Pi 5 호스트 설치

## 선정

Raspberry Pi 5 16GB를 고정 위치에 두고 전용 공유기를 통해 두 로봇과 통신한다.
기본 환경은 **Ubuntu Server 24.04 LTS arm64, ROS 2 Jazzy, 시스템 Python 3.12**로 확정한다.
Docker는 기본 실행 경로에서 사용하지 않는다. ROS는 apt 패키지를 쓰며 핵심 로직은
표준 Python으로 유지한다. ROS 메시지 변환·발행만 `ros2/` 어댑터가 담당한다.

Ubuntu의 Pi 5 지원과 Jazzy의 Ubuntu 24.04 arm64 Tier 1 패키지를 함께 사용할 수 있어
기존 가정을 유지한다. 서버 이미지로 GUI 상시 실행 부담을 줄이고, 네이티브 실행으로
DDS 탐색·네트워크·영상 장치 설정을 단순하게 한다. 이는 성능 측정 결과가 아닌 설계 선택이다.
ROS의 Python 확장 모듈과 ABI를 맞추기 위해 시스템 Python을 교체하지 않는다.

라이다 수신·모의 서버에는 추가 Python 의존성이 없다. 영상 추론 라이브러리·모델은
WP-X4에서 CPU 지연과 라이선스를 검증한 뒤 선정한다. 라이브러리 라이선스와 모델 가중치
라이선스는 따로 기록한다. SDK를 포함할 경우 BSD 2-Clause 고지를 보존하고, ROS·Ubuntu는
배포물 전체를 단일 라이선스로 간주하지 않고 사용 패키지별 고지를 유지한다.

근거: [Ubuntu Pi 지원표](https://ubuntu.com/hardware/docs/boards/how-to/ubuntu_supported/raspberry-pi/),
[Jazzy 지원 플랫폼·Python 기준](https://github.com/ros2/ros2_documentation/blob/jazzy/source/Releases/Release-Jazzy-Jalisco.rst),
[ROS apt 설치 안내](https://github.com/ros2/ros2_documentation/blob/jazzy/source/Installation/Ubuntu-Install-Debs.rst).

## 1. OS 준비

1. PC에서 Raspberry Pi Imager를 설치한다.
2. 장치를 Pi 5, OS를 Ubuntu Server **24.04 LTS 64-bit**로 선택한다.
   최신 OS 자동 선택 대신 버전과 arm64를 확인한다.
3. 대상 microSD 또는 SSD를 확인한 뒤 기록한다. 이 단계는 선택한 매체를 지운다.
4. 호스트 이름·사용자·SSH 공개키·전용 공유기 Wi-Fi를 설정한다. 자격 정보는 저장소에 넣지 않는다.
5. Pi 5에 전원·냉각·매체를 연결하고 부팅한다. 초기 설정 완료 후 SSH 또는 콘솔로 로그인한다.
6. 공유기에서 Pi와 두 로봇에 DHCP 예약을 설정한다. 로봇용 Wi-Fi는 2.4GHz를 지원해야 한다.

```bash
cat /etc/os-release
dpkg --print-architecture
python3 --version
sudo apt update
sudo apt full-upgrade
sudo apt install git curl locales software-properties-common python3-venv
sudo locale-gen en_US.UTF-8
sudo update-locale LANG=en_US.UTF-8
```

Ubuntu 24.04, arm64, Python 3.12인지 확인한다. 재부팅이 요구되면 재부팅 후 다시 로그인한다.

## 2. ROS 저장소와 Jazzy

아래는 Bash에서 실행한다. ROS 저장소 키와 설정은 공식 `ros2-apt-source` 패키지로 설치한다.

```bash
sudo add-apt-repository universe
export LANG=en_US.UTF-8
ros_source_version=$(curl -fsSL https://api.github.com/repos/ros-infrastructure/ros-apt-source/releases/latest | python3 -c 'import json,sys; print(json.load(sys.stdin)["tag_name"])')
curl -fL "https://github.com/ros-infrastructure/ros-apt-source/releases/download/${ros_source_version}/ros2-apt-source_${ros_source_version}.noble_all.deb" -o /tmp/ros2-apt-source.deb
sudo dpkg -i /tmp/ros2-apt-source.deb
sudo apt update
sudo apt install ros-jazzy-ros-base ros-jazzy-demo-nodes-cpp ros-jazzy-demo-nodes-py ros-dev-tools
source /opt/ros/jazzy/setup.bash
export ROS_DOMAIN_ID=42
export ROS_LOCALHOST_ONLY=1
```

ROS는 우선 Pi 내부에서 실행한다. 로봇은 DDS 참여자가 아닌 UDP/TCP 통신 상대이므로
이 설정은 로봇 연결을 막지 않는다. 원격 RViz가 필요하면 ROS 네트워크 설정을 별도로 변경한다.
apt 의존성 해결에 실패하면 공식 안내대로 `noble-updates`와 `noble-backports` 설정을 확인한다.
설치된 패키지 버전은 `dpkg-query -W 'ros-jazzy-*'`로 기록할 수 있다.

## 3. ROS만 동작 확인

터미널 1에서 `ros2 run demo_nodes_cpp talker`, 같은 환경 설정을 한 터미널 2에서
`ros2 run demo_nodes_py listener`를 실행한다. 수신을 확인하고 둘 다 Ctrl+C로 종료한다.
이 단계는 로봇이나 라이다에 연결하지 않는다.

## 4. 프로젝트와 PC 공통 테스트

```bash
mkdir -p ~/work
cd ~/work
git clone https://github.com/Lamed-D/Mechdog_Industry_Safety.git
cd Mechdog_Industry_Safety
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
python -m unittest discover -s tests
python -m tools.mock.mock_lidar
```

마지막 명령은 루프백 합성 서버만 실행한다. Ctrl+C로 종료한다.
ROS를 쓰지 않는 PC에서는 일반 venv로 충분하다. ROS 노드는 ROS 환경을 source하고
시스템 Python과 같은 마이너 버전으로 실행한다. 전역 pip 업데이트는 하지 않는다.

## 5. 다음 연결과 미검증 항목

라이다 사양은 [host-lidar.md](host-lidar.md), 중계와 배선은
[lidar-integration.md](lidar-integration.md)를 참조한다.
WP-X2에서 `/robot_a/scan`과 `/robot_b/scan` 어댑터와 실행 절차를 추가한다.
현재 해당 노드의 구현과 ROS 검증은 완료되지 않았다.
WP-X3 링크의 사용법과 v0 세션 경계 한계는 [host-link.md](host-link.md)에 명시한다.
WP-X4 영상은 장착 모듈의 공식 Python 결과와 원본 스트림을 구분해 적용한다.

실물 연결·명령 송신·로봇 업로드는 이 절차에 포함하지 않는다.
Pi 5에서는 아직 실행하지 않았다. 두 대 동시 스캔과 영상 추론의
CPU 부하·메모리·온도·지연을 측정하고 부족하면 Jetson으로 옮긴다.
이때 해당 JetPack이 지원하는 OS 기준으로 ROS 어댑터를 선정하며 Pi용 이미지를 쓰지 않는다.
핵심 로직과 합성 테스트는 유지하고 하드웨어에 종속된 추론 실행부만 교체한다.
