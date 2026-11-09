# 본체 I2C IMU만 공식 API로 읽습니다. MechDog·UART·Wi-Fi·고유 ID에 접근하지 않습니다.


def run(api=None, clock=None):
    if api is None:
        import Hiwonder_IIC as api
    if clock is None:
        import time as clock
    started = clock.ticks_ms()
    try:
        imu = api.MPU(api.IIC(1))
        value = imu.read_angle()
        if not isinstance(value, (list, tuple)) or len(value) < 2:
            raise ValueError("invalid_imu_shape")
        angles = value[:2]
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or v != v
               or v in (float("inf"), -float("inf")) for v in angles):
            raise ValueError("invalid_imu_value")
        return {"status": "read", "angles": list(angles), "result_type": type(value).__name__,
                "elapsed_ms": clock.ticks_diff(clock.ticks_ms(), started), "units_verified": False}
    except Exception as error:
        return {"status": "unknown", "error": type(error).__name__}


if __name__ == "__main__":
    print("수동 IMU 읽기 파일입니다. import 후 run을 호출하세요.")
