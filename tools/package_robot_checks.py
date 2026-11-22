"""PC에서 본체 시험 인계 폴더만 생성/검증합니다. 장치에는 접속하지 않습니다."""
import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "build/robot_checks"
REPO = "https://github.com/Lamed-D/Mechdog_Industry_Safety/blob/main/"
SCRIPTS = ("mechdog_only.py", "api_candidates.py", "robot_imu_check.py",
           "robot_loop_check.py", "vision_probe.py", "robot_motion_check.py")


def _github_link(match):
    # 인계 폴더 밖에서는 상대 링크가 깨지므로 저장소 주소로 바꿉니다.
    path = match.group(2) if match.group(1) else "docs/ai/" + match.group(2)
    return "](" + REPO + path


def contents():
    files = {name: (ROOT / "tools/bringup" / name).read_bytes() for name in SCRIPTS}
    guide = (ROOT / "docs/ai/robot-tests.md").read_text(encoding="utf-8")
    guide = re.sub(r"\]\((?!https?:)(\.\./\.\./)?([^)#]+)", _github_link, guide)
    files["README.md"] = guide.encode("utf-8")
    return files


def _folder(folder, allowed):
    folder = Path(folder)
    base = (ROOT / "build").resolve()
    if (folder.is_symlink() or getattr(folder, "is_junction", lambda: False)()
            or not base.is_relative_to(ROOT.resolve()) or not folder.resolve().is_relative_to(base)):
        raise ValueError("handoff output must stay inside workspace build")
    if folder.exists():
        for path in folder.iterdir():
            if path.name not in allowed or not path.is_file() or path.is_symlink():
                raise ValueError("unexpected handoff file; review manually")
    return folder


def package(folder=OUTPUT):
    files = contents()
    folder = _folder(folder, set(files) | {"manifest.json"})
    folder.mkdir(parents=True, exist_ok=True)
    for name, data in files.items():
        (folder / name).write_bytes(data)
    if contents() != files:
        raise ValueError("test sources changed during packaging")
    manifest = {"v": 1, "hardware_tested": False, "backup_status": "completed_user_report",
                "files": {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}}
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return folder


def verify(folder=OUTPUT):
    files = contents()
    folder = _folder(folder, set(files) | {"manifest.json"})
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    expected = {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}
    if (manifest.get("v") != 1 or manifest.get("hardware_tested") is not False
            or manifest.get("backup_status") != "completed_user_report" or manifest.get("files") != expected
            or any((folder / name).read_bytes() != data for name, data in files.items())):
        raise ValueError("handoff files do not match current tests")
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if not args.verify:
        package()
    verify()
    print("verified build/robot_checks; 6 test scripts; no main.py; no device access")


if __name__ == "__main__":
    main()
