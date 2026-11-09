# 실물 확인 4 (로봇 쪽): Wi-Fi 접속 + UDP 되돌려 보내기. 로봇을 움직이지 않습니다.
# secrets.py(WIFI_SSID, WIFI_PASSWORD)를 같이 올려 두고 실행합니다. 끝나면 PC·Pi 5 에서
#   python tools/bringup/rtt_probe.py <로봇IP>
# 로 왕복 지연을 잽니다. PM_NONE 을 쓰지 않은 경우와 비교하려면 USE_PM_NONE 을 False 로 바꿔 한 번 더 잽니다.

import socket
import time

import network

PORT = 9100
USE_PM_NONE = True
RUN_SECONDS = 120


def connect():
    import secrets
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if USE_PM_NONE:
        try:
            wlan.config(pm=network.WLAN.PM_NONE)
            print("PM_NONE: ok")
        except Exception as error:
            print("PM_NONE: not supported", repr(error))
    wlan.connect(secrets.WIFI_SSID, secrets.WIFI_PASSWORD)
    start = time.ticks_ms()
    while not wlan.isconnected():
        if time.ticks_diff(time.ticks_ms(), start) > 15000:
            print("wifi: timeout")
            return None
        time.sleep_ms(200)
    print("wifi: ok", wlan.ifconfig(), "in", time.ticks_diff(time.ticks_ms(), start), "ms")
    return wlan


def echo(seconds=RUN_SECONDS):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", PORT))
    sock.settimeout(0.5)
    count = 0
    end = time.ticks_add(time.ticks_ms(), seconds * 1000)
    while time.ticks_diff(end, time.ticks_ms()) > 0:
        try:
            data, addr = sock.recvfrom(128)
        except OSError:
            continue
        sock.sendto(data, addr)
        count += 1
    sock.close()
    print("echoed", count)


def main():
    if connect() is not None:
        echo()


if __name__ == "__main__":
    main()
