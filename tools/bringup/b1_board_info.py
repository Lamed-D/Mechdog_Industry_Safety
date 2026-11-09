# 실물 확인 1: 펌웨어·공식 모듈·필요 기능이 있는지 봅니다. 로봇을 움직이지 않습니다.
# MechDog 객체를 만들지 않고 클래스에 메서드가 있는지만 봅니다(만들 때 자세를 잡을 수 있어서).
# REPL 에 붙여 넣거나 Python Editor 로 실행합니다. 결과를 docs/bringup.md 의 표에 적습니다.

import sys


def check(label, func):
    try:
        value = func()
        print("OK  ", label, value)
        return True
    except Exception as error:
        print("FAIL", label, repr(error))
        return False


def has(module_name, attr):
    module = __import__(module_name)
    for part in attr.split("."):
        module = getattr(module, part)
    return True


def main():
    print("sys.version =", sys.version)
    print("sys.implementation =", sys.implementation)
    check("import HW_MechDog", lambda: __import__("HW_MechDog") and True)
    for name in ("move", "action_run", "set_default_pose", "action_is_over", "stop_action",
                 "homeostasis", "read_homeostasis_status"):
        check("MechDog." + name, lambda name=name: has("HW_MechDog", "MechDog." + name))
    for attr in ("startMain", "Battery_power", "Buzzer"):
        check("Hiwonder." + attr, lambda attr=attr: has("Hiwonder", attr))
    check("Hiwonder.Battery_power()", lambda: __import__("Hiwonder").Battery_power())
    check("Hiwonder_IIC.MPU(IIC(1)).read_angle()",
          lambda: __import__("Hiwonder_IIC").MPU(__import__("Hiwonder_IIC").IIC(1)).read_angle())
    check("network.WLAN.PM_NONE", lambda: __import__("network").WLAN.PM_NONE)
    check("machine.UART(1, 115200, rx=32, tx=33, rxbuf=4096)", open_lidar_uart)
    check("machine.unique_id()", lambda: __import__("machine").unique_id())


def open_lidar_uart():
    import machine
    uart = machine.UART(1, baudrate=115200, rx=32, tx=33, rxbuf=4096)
    try:
        uart.deinit()
    except Exception:
        pass
    return "opened"


if __name__ == "__main__":
    main()
