# 실물 확인 3: 라이다 응답. 라이다 TX→J5-4(IO32), RX→J5-3(IO33), GND 공통, 전원은 별도 5V.
# STOP → GET_HEALTH → GET_INFO 를 보내고 응답을 풀어 보여 줍니다. 로봇을 움직이지 않습니다.
# 응답 형식(시작 A5 5A, 7바이트 머리)은 공개 프로토콜 기준.

import time

import machine

STOP = b"\xa5\x25"
GET_HEALTH = b"\xa5\x52"
GET_INFO = b"\xa5\x50"
HEALTH_NAMES = {0: "Good", 1: "Warning", 2: "Error"}


def read_exact(uart, size, timeout_ms=500):
    data = b""
    start = time.ticks_ms()
    while len(data) < size and time.ticks_diff(time.ticks_ms(), start) < timeout_ms:
        chunk = uart.read(size - len(data))
        if chunk:
            data += chunk
        else:
            time.sleep_ms(5)
    return data


def request(uart, command, size):
    """명령을 보내고 (머리 7바이트, 본문) 을 돌려줍니다. 실패하면 None."""
    while uart.any():
        uart.read()
    uart.write(command)
    head = read_exact(uart, 7)
    if len(head) != 7 or head[:2] != b"\xa5\x5a":
        print("bad header:", head)
        return None
    body = read_exact(uart, size)
    if len(body) != size:
        print("short body:", body)
        return None
    return head, body


def parse_health(body):
    return HEALTH_NAMES.get(body[0], "unknown(%d)" % body[0]), body[1] | (body[2] << 8)


def parse_info(body):
    serial = "".join("%02X" % b for b in body[4:20])
    return {"model": body[0], "firmware": "%d.%02d" % (body[2], body[1]),
            "hardware": body[3], "serial": serial}


def main():
    uart = machine.UART(1, baudrate=115200, rx=32, tx=33, rxbuf=4096)
    uart.write(STOP)
    time.sleep_ms(20)
    health = request(uart, GET_HEALTH, 3)
    if health:
        print("health:", parse_health(health[1]))
    info = request(uart, GET_INFO, 20)
    if info:
        print("info:", parse_info(info[1]))
    return health is not None and info is not None


if __name__ == "__main__":
    main()
