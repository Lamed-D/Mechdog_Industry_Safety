"""실물 확인 5 (PC·Pi 5 쪽): 비전 모듈 영상 주소가 열리는지, 몇 바이트가 오는지 봅니다.

    python tools/bringup/camera_check.py http://<비전모듈IP>:<포트>/<경로> [--seconds 5]

비전 모듈 기본 펌웨어의 실제 영상 주소는 실물에서 확인해야 합니다([확인 필요]).
ESP32 카메라 예제에서 흔한 형태는 MJPEG 스트림(`multipart/x-mixed-replace`)입니다.
영상은 저장하지 않습니다(사람 얼굴이 찍힐 수 있음). 받은 바이트 수와 JPEG 시작 표시 수만 셉니다.
"""

import argparse
import time
import urllib.request

JPEG_START = b"\xff\xd8"


def count_frames(stream, seconds, chunk=4096):
    total = 0
    frames = 0
    tail = b""
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        data = stream.read(chunk)
        if not data:
            break
        total += len(data)
        joined = tail + data
        frames += joined.count(JPEG_START) - tail.count(JPEG_START)
        tail = joined[-1:]
    return total, frames


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("url")
    parser.add_argument("--seconds", type=float, default=5.0)
    args = parser.parse_args()
    with urllib.request.urlopen(args.url, timeout=5) as response:
        print("status", response.status, "type", response.headers.get("Content-Type"))
        total, frames = count_frames(response, args.seconds)
    print("bytes %d, jpeg frames %d, fps %.1f" % (total, frames, frames / args.seconds))


if __name__ == "__main__":
    main()
