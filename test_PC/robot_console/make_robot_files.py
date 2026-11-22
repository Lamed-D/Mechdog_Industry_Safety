"""로봇 메인 보드에 Python Editor로 올릴 작은 파일들을 만듭니다(장치에 접속하지 않음).

robot/ 와 custom_sensors/lidar_bridge.py 를 주석·설명문 없이, 영문(ASCII)만, 짧은 줄로 바꿔
build/robot_files_<ID>/ 에 파일별로 씁니다. 동작 코드는 그대로입니다.
한 파일로 묶은 큰 main.py(tools/bundle_robot.py)는 편집기 전송이 실패해서 이 방식을 씁니다.

실행: python -m test_PC.robot_console.make_robot_files B
"""
import ast
import io
import re
import sys
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.bundle_robot import MODULES  # noqa: E402

UPLOAD_ORDER = ("netutil", "motion", "roles", "config", "proto", "vision", "comm",
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
        folder = "custom_sensors" if name == "lidar_bridge" else "robot"
        text = strip((ROOT / folder / (name + ".py")).read_text(encoding="utf-8"))
        if name == "config":
            text, count = re.subn(r'^ROBOT_ID = "[AB]"$', 'ROBOT_ID = "%s"' % robot, text, flags=re.M)
            if count != 1:
                raise ValueError("ROBOT_ID line not found")
        text.encode("ascii")
        compile(text, name + ".py", "exec")
        files[name + ".py"] = text
    return files


def main():
    robot = sys.argv[1] if len(sys.argv) > 1 else "B"
    out = ROOT / "build" / ("robot_files_" + robot)
    out.mkdir(parents=True, exist_ok=True)
    files = render(robot)
    for name, text in files.items():
        (out / name).write_text(text, encoding="ascii", newline="\n")
    print("만듦:", out)
    print("올리는 순서:", " -> ".join(n + ".py" for n in UPLOAD_ORDER), "(secrets.py 는 따로)")


if __name__ == "__main__":
    main()
