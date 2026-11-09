"""사용자용 카메라 수신/처리 측정. 영상·사진을 저장하거나 로봇 명령을 보내지 않습니다."""
import argparse
from collections import deque
import importlib
import io
import json
import math
import os
import time

from host.vision.camera_client import CameraEndpoint, LatestFrameReceiver
from host.vision.pipeline import jpeg_size


def percentile(values, fraction=.95):
    ordered = sorted(values)
    return round(ordered[max(0, math.ceil(len(ordered) * fraction) - 1)], 2) if ordered else None


def measure(receivers, duration_s, *, processor=None, clock=time.monotonic, sleep=time.sleep):
    if not math.isfinite(duration_s) or duration_s <= 0:
        raise ValueError("positive finite measurement duration required")
    start = clock()
    initial = {r: (rx.frames, rx.bytes_received) for r, rx in receivers.items()}
    stats = {r: {"selected": 0, "processed": 0, "errors": 0, "age": deque(maxlen=2000), "latency": deque(maxlen=2000),
                 "dimensions": None, "last": None} for r in receivers}
    while clock() - start < duration_s:
        for robot, rx in receivers.items():
            frame = rx.latest()
            st = stats[robot]
            if frame is None or st["last"] == (frame.seq, frame.captured_at):
                continue
            st["last"] = (frame.seq, frame.captured_at)
            st["selected"] += 1
            st["dimensions"] = jpeg_size(frame.jpeg)
            before = clock()
            if processor is not None:
                try:
                    processor(frame.jpeg)
                    st["processed"] += 1
                except Exception:
                    st["errors"] += 1
                st["latency"].append((clock() - before) * 1000)
            st["age"].append((clock() - frame.captured_at) * 1000)
        sleep(.01)
    elapsed = clock() - start
    result = {"elapsed_s": round(elapsed, 3), "processor_configured": processor is not None,
              "model_accuracy_verified": False, "percentile_window_samples": 2000, "robots": {}}
    for robot, rx in receivers.items():
        st = stats[robot]
        result["robots"][robot] = {"received_fps": round((rx.frames - initial[robot][0]) / elapsed, 2),
            "jpeg_kbps": round((rx.bytes_received - initial[robot][1]) * 8 / elapsed / 1000, 2),
            "selected_frames": st["selected"], "processed_fps": round(st["processed"] / elapsed, 2),
            "processing_errors": st["errors"], "processing_ms_p95": percentile(st["latency"]),
            "result_age_ms_p95": percentile(st["age"]), "dimensions": st["dimensions"], "state": rx.state()}
    return result


def decode_jpeg(data):
    from PIL import Image  # --decode 시에만 선택 의존성 Pillow가 필요합니다.
    with Image.open(io.BytesIO(data)) as image:
        image.convert("RGB").load()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--a-host", required=True)
    parser.add_argument("--b-host", required=True)
    parser.add_argument("--allow-camera", action="store_true", help="실제 카메라 영상 읽기를 명시적으로 허용")
    parser.add_argument("--seconds", type=float, default=30)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--decode", action="store_true", help="선택 Pillow JPEG→RGB 디코딩 시간 측정")
    mode.add_argument("--processor", help="사용자가 설치/검토한 module:function(JPEG bytes) 처리 시간 측정")
    args = parser.parse_args()
    if not args.allow_camera or not math.isfinite(args.seconds) or not 1 <= args.seconds <= 3600:
        parser.error("--allow-camera와 1~3600초 측정 시간이 필요합니다")
    if args.a_host == args.b_host:
        parser.error("두 로봇 카메라의 주소를 구분해야 합니다")
    processor = decode_jpeg if args.decode else None
    if args.processor:
        module, separator, name = args.processor.partition(":")
        if not separator:
            parser.error("--processor는 module:function 형식입니다")
        processor = getattr(importlib.import_module(module), name)
        if not callable(processor):
            parser.error("processor must be callable")
    if args.decode:
        import PIL  # 시작 전에 설치 확인; 자동 설치하지 않습니다.
    receivers = {}
    try:
        for robot, host in (("A", args.a_host), ("B", args.b_host)):
            endpoint = CameraEndpoint(robot, host, key=os.environ.get("CAMERA_" + robot + "_KEY"))
            receivers[robot] = LatestFrameReceiver(endpoint).start()
        print(json.dumps(measure(receivers, args.seconds, processor=processor), ensure_ascii=False, indent=2))
    finally:
        for rx in receivers.values():
            rx.stop()


if __name__ == "__main__":
    main()
