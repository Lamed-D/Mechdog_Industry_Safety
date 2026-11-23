"""본체용 secrets.py의 Wi-Fi 값을 굽기가 끝난 카메라에 USB로 저장합니다."""
import argparse
import ast
from time import monotonic

from .make_robot_files import validate_wifi, wifi_file


def read_wifi(robot):
    try:
        tree = ast.parse(wifi_file(robot).read_text(encoding="utf-8"))
        values = {statement.targets[0].id: ast.literal_eval(statement.value)
                  for statement in tree.body if isinstance(statement, ast.Assign)
                  and isinstance(statement.targets[0], ast.Name)}
        ssid, password = values["WIFI_SSID"], values["WIFI_PASSWORD"]
        validate_wifi(ssid, password)
    except (OSError, UnicodeError, SyntaxError, ValueError, KeyError):
        raise SystemExit("Wi-Fi 설정을 읽지 못했습니다. 빌드에 --wifi-setup을 지정해 다시 만드세요.") from None
    return ssid, password


def expect(port, marker):
    deadline = monotonic() + 8
    while monotonic() < deadline:
        if port.readline().strip().startswith(marker):
            return
    raise SystemExit("카메라 응답을 확인하지 못했습니다. 포트와 펌웨어를 확인한 뒤 다시 실행하세요.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("robot", type=str.upper, choices=("A", "B"))
    parser.add_argument("--port", required=True, help="굽기를 마친 카메라 USB 포트 (예: COM7)")
    args = parser.parse_args()
    ssid, password = read_wifi(args.robot)
    try:
        import serial
    except ImportError:
        parser.exit(1, "먼저 python -m pip install pyserial 을 실행하세요.\n")
    try:
        with serial.Serial(args.port, 115200, timeout=0.25, write_timeout=2) as port:
            port.reset_input_buffer()
            port.write(b"\nhelp\n")
            expect(port, "[cfg] 명령 (줄 끝 Enter, 115200bps):".encode("utf-8"))
            for field, value in (("robot", args.robot), ("ssid", ssid), ("pass", password)):
                port.write(f"set {field} {value}\n".encode("utf-8"))
                expect(port, f"[cfg] {field} 저장 완료.".encode("utf-8"))
            port.write(b"reboot\n")
            expect(port, "[cfg] 다시 시작합니다".encode("utf-8"))
    except serial.SerialException:
        raise SystemExit("카메라 USB 통신에 실패했습니다. COM 포트와 시리얼 모니터를 확인하세요.") from None
    print(f"로봇 {args.robot} 카메라 Wi-Fi 저장 완료. 재부팅 후 /status에서 접속을 확인하세요.")


if __name__ == "__main__":
    main()
