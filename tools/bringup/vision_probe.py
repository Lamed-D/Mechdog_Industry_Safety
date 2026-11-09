# Vision-only diagnostic for the MechDog main board, not the camera firmware.
# Uses the official Python camera API. No MechDog object, motion, BLE, or reset.


def run(api, clock):
    print("VISION_ONLY_BEGIN")
    if not hasattr(api, "ESP32S3Cam"):
        result = {"status": "unknown", "reason": "camera_api_missing"}
        print("VISION_RESULT", result)
        print("VISION_ONLY_END")
        return result
    stage = "iic_init"
    try:
        print("VISION_STAGE", stage)
        bus = api.IIC(2)
        stage = "camera_init"
        print("VISION_STAGE", stage)
        camera = api.ESP32S3Cam(bus)
        print("VISION_METHODS", [name for name in ("face_recognition", "color_recognition")
                                 if callable(getattr(camera, name, None))])
        stage = "warmup"
        clock.sleep_ms(1000)
        stage = "face_read"
        print("VISION_STAGE", stage)
        started = clock.ticks_ms()
        value = camera.face_recognition()
        elapsed = clock.ticks_diff(clock.ticks_ms(), started)
        result = {"status": "observed" if value is not None else "unknown",
                  "result_type": type(value).__name__,
                  "has_result": bool(value), "read_ms": elapsed,
                  "fallen_person": "unknown"}
    except Exception as error:
        args = getattr(error, "args", ())
        number = args[0] if args and isinstance(args[0], int) and not isinstance(args[0], bool) else None
        result = {"status": "unknown", "reason": "camera_call_failed",
                  "stage": stage, "error_type": type(error).__name__, "errno": number}
    print("VISION_RESULT", result)
    print("VISION_ONLY_END")
    return result


def main():
    import Hiwonder_IIC
    import time
    return run(Hiwonder_IIC, time)


if __name__ == "__main__":
    main()
