"""장치에 연결하지 않고 robot 코드를 build/robot_<ID>/main.py로 묶습니다."""
import argparse
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULES = ("config", "proto", "roles", "netutil", "motion", "vision", "lidar_bridge", "core", "comm", "app", "main")


def render(robot):
    if robot not in ("A", "B"):
        raise ValueError("robot must be A or B")
    # 별도 전역 사전으로 이름 충돌을 막고, 사용자 모듈 import를 메모리 안 참조로 바꿉니다.
    lines = ["# 생성 파일: 직접 수정하지 말고 tools/bundle_robot.py로 다시 만드세요.",
             "class _BundleModule:",
             "    def __init__(self, values): self.values = values",
             "    def __getattr__(self, name):",
             "        if name not in self.values: raise AttributeError(name)",
             "        return self.values[name]",
             "_bundle_modules = {}"]
    for name in MODULES:
        folder = "custom_sensors" if name == "lidar_bridge" else "robot"
        source = (ROOT / folder / (name + ".py")).read_text(encoding="utf-8")
        tree = ast.parse(source)
        body = source.splitlines()
        bindings = []
        for node in tree.body:
            if isinstance(node, ast.Import):
                internal = [a for a in node.names if a.name in MODULES]
                if internal:
                    if len(internal) != len(node.names):
                        raise ValueError("mixed import requires explicit support")
                    bindings.extend((a.asname or a.name, a.name, None) for a in internal)
                else:
                    continue
            elif isinstance(node, ast.ImportFrom) and node.module in MODULES:
                if any(a.name == "*" for a in node.names):
                    raise ValueError("wildcard import unsupported")
                bindings.extend((a.asname or a.name, node.module, a.name) for a in node.names)
            else:
                continue
            for i in range(node.lineno - 1, node.end_lineno):
                body[i] = ""
        lines.append("_bundle_globals = {'__name__': %r}" % name)
        for alias, module, attr in bindings:
            value = "_bundle_modules[%r]" % module
            if attr:
                value += "." + attr
            lines.append("_bundle_globals[%r] = %s" % (alias, value))
        lines.append("exec(%r, _bundle_globals)" % "\n".join(body))
        if name == "config":
            lines.append("_bundle_globals['ROBOT_ID'] = %r" % robot)
        lines.append("_bundle_modules[%r] = _BundleModule(_bundle_globals)" % name)
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--robot", choices=("A", "B"), required=True)
    args = parser.parse_args()
    output = ROOT / "build" / ("robot_" + args.robot) / "main.py"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render(args.robot), encoding="utf-8")
    print("generated", output.relative_to(ROOT), output.stat().st_size, "bytes; no device access")


if __name__ == "__main__":
    main()
