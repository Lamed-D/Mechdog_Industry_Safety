"""로봇 메인 보드에 Python Editor로 올릴 작은 파일들을 만듭니다(장치에 접속하지 않음).

firmware/robot/python/ 을 주석·설명문 없이, 영문(ASCII)만, 짧은 줄로 바꿔
build/robot_<ID>/python/ 에 파일별로 씁니다. 동작 코드는 그대로입니다.

실행: python firmware/builder/make_robot_files.py B
(펌웨어 전체를 로봇별로 한 번에: python firmware/build.py <A|B>)
"""
import ast
from getpass import GetPassWarning, getpass
import io
import re
import sys
from tempfile import NamedTemporaryFile
import warnings
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
MODULES = ("config", "proto", "roles", "netutil", "motion", "vision", "sonar", "lidar_bridge", "core", "comm", "app",
           "main")

UPLOAD_ORDER = ("netutil", "motion", "roles", "config", "proto", "vision", "sonar", "comm",
                "lidar_bridge", "core", "app", "main")  # main.py 는 반드시 마지막


def strip(source):
    """설명문은 pass 로, 주석·빈 줄은 제거합니다."""
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) \
                    and isinstance(first.value.value, str):
                indent = lines[first.lineno - 1][:first.col_offset]
                for i in range(first.lineno - 1, first.end_lineno):
                    lines[i] = ""
                lines[first.lineno - 1] = indent + "pass"
    source = "\n".join(lines) + "\n"
    tokens = [t for t in tokenize.generate_tokens(io.StringIO(source).readline) if t.type != tokenize.COMMENT]
    source = tokenize.untokenize(tokens)
    return "\n".join(l.rstrip() for l in source.splitlines() if l.strip()) + "\n"


def render(robot):
    """{파일 이름: 내용}. 모두 ASCII 이며 컴파일됩니다."""
    if robot not in ("A", "B"):
        raise ValueError("robot must be A or B")
    files = {}
    for name in MODULES:
        folder = "firmware/robot/python"
        text = strip((ROOT / folder / (name + ".py")).read_text(encoding="utf-8"))
        if name == "config":
            text, count = re.subn(r'^ROBOT_ID = "[AB]"$', 'ROBOT_ID = "%s"' % robot, text, flags=re.M)
            if count != 1:
                raise ValueError("ROBOT_ID line not found")
        text.encode("ascii")
        compile(text, name + ".py", "exec")
        files[name + ".py"] = text
    return files


def output_dir(robot):
    return ROOT / "build" / ("robot_" + robot) / "python"


def wifi_file(robot):
    return output_dir(robot).parent / "wifi" / "secrets.py"


def validate_wifi(ssid, password):
    for value, limit in ((ssid, 32), (password, 63)):
        if (not isinstance(value, str) or not 1 <= len(value.encode("utf-8")) <= limit
                or any(char in value for char in "\r\n\0")):
            raise ValueError("Wi-Fi 이름은 1~32바이트, 비밀번호는 1~63바이트로 입력하세요.")


def configure_wifi(robot):
    """본체에 따로 올릴 Wi-Fi 설정을 만듭니다."""
    if not sys.stdin.isatty():
        raise ValueError("--wifi-setup은 대화형 터미널에서 실행하세요.")
    path = wifi_file(robot)
    folder = path.parent
    if not folder.resolve().is_relative_to(ROOT.resolve()):
        raise ValueError("Wi-Fi 설정 폴더가 작업 폴더 밖입니다.")
    try:
        ssid = input("Wi-Fi 이름(SSID): ")
        with warnings.catch_warnings():
            warnings.simplefilter("error", GetPassWarning)
            password = getpass("Wi-Fi 비밀번호: ")
    except (EOFError, KeyboardInterrupt, GetPassWarning):
        raise ValueError("Wi-Fi 설정 입력을 완료하지 못했습니다. 기존 설정은 유지됩니다.") from None
    validate_wifi(ssid, password)

    folder.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(mode="w", encoding="ascii", newline="\n",
                            dir=folder, delete=False) as temporary:
        pending = Path(temporary.name)
    try:
        pending.write_text(f"WIFI_SSID = {ascii(ssid)}\nWIFI_PASSWORD = {ascii(password)}\n",
                           encoding="ascii", newline="\n")
        pending.replace(path)
    finally:
        pending.unlink(missing_ok=True)
    print("Wi-Fi 설정 파일:", path)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    robot = argv[0].upper() if argv else "B"
    files = render(robot)
    out = output_dir(robot)
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("*.py"):  # 이전 빌드에만 있던 파일이 섞여 올라가지 않게
        if old.name not in files:
            old.unlink()
    for name, text in files.items():
        (out / name).write_text(text, encoding="ascii", newline="\n")
    print("만듦:", out)
    print("올리는 순서:", " -> ".join(n + ".py" for n in UPLOAD_ORDER), "(secrets.py 는 따로)")
    return out


if __name__ == "__main__":
    main()
