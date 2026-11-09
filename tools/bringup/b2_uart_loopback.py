# 실물 확인 2: J5 UART 루프백. J5-3(IO33)과 J5-4(IO32)를 점퍼선으로 잇고(라이다는 빼고) 실행합니다.
# 로봇을 움직이지 않습니다. 정상이면 보낸 바이트가 그대로 돌아옵니다.

import time

import machine

PATTERN = bytes(range(256))


def main():
    uart = machine.UART(1, baudrate=115200, rx=32, tx=33, rxbuf=4096)
    for _ in range(16):
        if not uart.any():
            break
        uart.read(512)
    uart.write(PATTERN)
    time.sleep_ms(100)  # 256 바이트 @115200 ≈ 22 ms
    got = uart.read() or b""
    ok = got == PATTERN
    print("sent", len(PATTERN), "got", len(got), "match", ok)
    if not ok:
        print("first bytes:", got[:16])
    return ok


if __name__ == "__main__":
    main()
