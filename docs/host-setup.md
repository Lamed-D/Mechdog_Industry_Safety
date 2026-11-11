# Pi 5 호스트 설치

## 선정

Raspberry Pi 5 16GB를 고정 위치에 두고 내장 Wi-Fi 핫스팟으로 두 로봇과 통신한다.
인터넷은 유선 랜·USB Wi-Fi·USB 테더링 중 별도 장치로 받으며 전용 공유기는 핫스팟 장애 시 예비다.
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
4. 호스트 이름·사용자·SSH 공개키와 별도 인터넷 연결을 준비한다. 자격 정보는 저장소에 넣지 않는다.
5. Pi 5에 전원·냉각·매체를 연결하고 부팅한다. 초기 설정 완료 후 SSH 또는 콘솔로 로그인한다.
6. 아래 6절에서 Pi 내장 Wi-Fi를 2.4GHz AP로 설정하고 두 본체·두 카메라 주소를 예약한다.

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

## 6. 로봇망 핫스팟 + 별도 인터넷 (사용자 실행용, 미검증)

이 절차는 문서만 준비했으며 Pi에서 실행하지 않았다. 실제 네트워크 변경·비밀번호 입력·장치 연결은 사용자만 한다.
로봇 전원을 끄고 Pi의 로컬 콘솔에서 준비한다. AP 전환으로 기존 Wi-Fi SSH가 끊길 수 있다.
사용자는 기존 Netplan/NetworkManager 설정을 로컬에 백업하고 변경 전 연결로 복구할 수 있어야 한다.

### 6.1 장치와 관리 주체 확인

```bash
ip -br link
ip -4 route
nmcli --version
nmcli device status
nmcli -f GENERAL.DEVICE,WIFI-PROPERTIES.AP device show wlan0
```

`wlan0`는 예시이며 실제 내장 Wi-Fi 이름으로 바꾼다. AP 지원 여부와 국가별 허용 채널을 확인한다.
로봇망과 인터넷 주소 대역이 겹치면 아래 예시 대역 전체를 함께 바꾼다. 한 무선 장치의 AP/인터넷 동시 사용은 하지 않는다.
Ubuntu Server의 networkd가 wlan0를 관리하면 기존 Netplan에서 그 장치의 renderer를 NetworkManager로 조정한다.
다른 장치의 설정을 덮어쓰지 말고 로컬 콘솔에서 `sudo netplan try`로 검증한 뒤 진행한다.
NetworkManager 미설치 시 사용자가 `network-manager`를 설치한다. wlan0가 managed이고 AP 가능일 때만 다음으로 간다.
근거: [Netplan renderer](https://netplan.readthedocs.io/en/latest/netplan-yaml/).

### 6.2 주소 계획

| 대상 | 예시 주소 | 할당 |
| --- | --- | --- |
| Pi 내장 AP | `10.42.0.1/24` | 수동 고정, 기본 게이트웨이 없음 |
| 본체 A / B | `10.42.0.11` / `10.42.0.12` | 사용자 확인한 MAC에 DHCP 예약 |
| 카메라 A / B | `10.42.0.21` / `10.42.0.22` | 사용자 확인한 MAC에 DHCP 예약 |
| 초기 확인용 DHCP | `.100`~`.149` | 임시 접속, 운영 시 위 예약 주소 확인 |
| Pi 인터넷 장치 | 건물망/테더링 DHCP | 로봇망과 별도 대역, Pi의 기본 경로 |
| 관리자 노트북 | 별도 인터넷 | AP에 접속하지 않고 Supabase만 사용 |

MAC·실제 주소·SSID·비밀번호·임대 기록은 Pi 로컬에만 둔다. 공개 결과에는 실제 식별 정보를 붙이지 않는다.

### 6.3 인터넷 공유 없는 AP

일반 `nmcli device wifi hotspot`/`ipv4.method shared`는 DHCP와 NAT/포워딩을 함께 켤 수 있으므로 사용하지 않는다.
수동 IPv4 AP와 DHCP 전용 dnsmasq를 분리한다. 아래 AP 생성·활성화는 사용자 작업이다.

```bash
sudo nmcli connection add type wifi ifname wlan0 con-name mechdog-robot-ap ssid '<ROBOT_SSID>'
sudo nmcli connection modify mechdog-robot-ap \
  802-11-wireless.mode ap 802-11-wireless.band bg 802-11-wireless.channel 6 \
  802-11-wireless-security.key-mgmt wpa-psk 802-11-wireless-security.proto rsn \
  802-11-wireless-security.pairwise ccmp 802-11-wireless-security.group ccmp \
  802-11-wireless-security.psk-flags 2 \
  ipv4.method manual ipv4.addresses 10.42.0.1/24 ipv4.never-default yes \
  ipv6.method disabled connection.autoconnect no
sudo nmcli --ask connection up mechdog-robot-ap
```

채널 6은 예시이며 1·6·11 중 현장 혼잡/국가 설정을 확인해 선택한다. `--ask`에서 사용자만 WPA2 암호를 입력한다.
예시는 암호를 저장하지 않으므로 재부팅 후 사용자가 다시 활성화한다. 무인 자동 시작이 필요하면 사용자가
권한 제한된 로컬 비밀 저장 방식을 별도 구성한다. 암호를 명령줄/저장소에 기록하지 않는다.
근거: [Ubuntu 24.04 NM 설정](https://manpages.ubuntu.com/manpages/noble/man5/nm-settings-nmcli.5.html),
[nmcli --ask](https://manpages.ubuntu.com/manpages/noble/man1/nmcli.1.html).

### 6.4 DHCP만 제공

사용자가 `dnsmasq-base`를 설치하고 아래 내용을 `/etc/mechdog/robot-dhcp.conf`에 만든다.
디렉터리/파일은 root만 수정하게 한다. 기존 DHCP 서버와 중복 실행하지 않는다.
예약의 MAC 자리표시는 실제 확인값으로 교체하며 저장소에 넣지 않는다.

```ini
port=0
interface=wlan0
bind-dynamic
dhcp-range=10.42.0.100,10.42.0.149,255.255.255.0,12h
dhcp-option=option:router
dhcp-option=option:dns-server
dhcp-host=<MAIN_A_MAC>,10.42.0.11
dhcp-host=<MAIN_B_MAC>,10.42.0.12
dhcp-host=<CAM_A_MAC>,10.42.0.21
dhcp-host=<CAM_B_MAC>,10.42.0.22
```

```bash
sudo dnsmasq --test --conf-file=/etc/mechdog/robot-dhcp.conf
sudo dnsmasq --no-daemon --conf-file=/etc/mechdog/robot-dhcp.conf
```

두 번째 명령은 별도 로컬 터미널에서 유지하며 Ctrl+C로 종료한다. DNS와 기본 경로를 배포하지 않고 DHCP만 제공한다.
부팅 서비스화는 수동 연결·주소 검증 후 사용자 운영 설정으로 진행한다.
근거: [dnsmasq 공식 매뉴얼](https://thekelleys.org.uk/dnsmasq/docs/dnsmasq-man.html).

### 6.5 분리 확인과 다음 단계

사용자는 Pi의 IPv4 `net.ipv4.ip_forward=0`, IPv6 `net.ipv6.conf.all.forwarding=0`을 확인하고 유지한다.
로봇망과 외부 장치를 브리지로 묶지 않으며 NAT·포트포워딩·터널을 만들지 않는다.
기존 방화벽은 유지하고 AP를 출발/목적으로 하는 FORWARD를 차단한다. 로봇망에서 Pi로 들어오는 DHCP/텔레메트리만
필요에 맞게 허용하고, TCP 라이다·카메라는 Pi가 클라이언트다. 인터넷 장치에서는 로봇 포트를 받지 않는다.
기존 방화벽 관리 방식이 달라질 수 있어 규칙 전체 초기화 명령은 제공하지 않는다.

```bash
ip -4 address show dev wlan0
ip -4 route
sysctl net.ipv4.ip_forward net.ipv6.conf.all.forwarding
nmcli -f ipv4.method,ipv4.never-default,802-11-wireless.band,802-11-wireless.mode connection show mechdog-robot-ap
```

Pi 기본 경로가 인터넷 장치에만 있고 AP는 `10.42.0.0/24` 직접 경로만 있어야 한다.
사용자가 본체/카메라 예약 주소와 Pi 통신을 확인하고 로봇망의 외부 인터넷 차단을 별도 점검한다.
기록은 로컬에만 남기고 비밀번호·MAC·실제 영상은 공유하지 않는다. AP 중단은 사용자 콘솔에서
`sudo nmcli connection down mechdog-robot-ap` 후 DHCP 터미널을 종료한다. 로봇 구동 중에는 수행하지 않는다.

Supabase는 Pi가 HTTPS로 밖에만 연결한다. 실제 계정/키·SQL/RLS·비공개 Storage 확인은 사용자 단계다.
장비 없는 검증은 `python -m tools.mock.hub_cloud_demo`와 unittest를 사용한다.
두 영상·라이다 동시 부하, AP 재부팅/인터넷 단절, 실측 약한 링크 기준과 600ms 정지는 실물 미검증이다.
