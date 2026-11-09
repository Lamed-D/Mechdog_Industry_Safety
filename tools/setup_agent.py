"""에이전트 작업 폴더 초기 설정: 이름 지정, 커밋 검사 훅 설치, 준비 상태 확인.

클론(또는 git worktree)을 만든 직후, 그 폴더에서 사람이 한 번 실행한다.

    python tools/setup_agent.py claude2          # 이름 지정 + 훅 설치 + 점검
    python tools/setup_agent.py claude2 --labels # GitHub 라벨 from:/to:<이름> 도 만든다 (gh 로그인 필요)
    python tools/setup_agent.py --show           # 현재 설정만 확인

에이전트는 자기 이름을 다음 명령으로 읽는다.

    git config --get agent.name

이름은 이 작업 폴더에만 저장된다(git worktree 별 설정). 저장소에 커밋되지 않는다.
"""

import argparse
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
NAME_RE = re.compile(r"^(claude|codex)[1-9][0-9]?$")
REPO = "Lamed-D/Mechdog_Industry_Safety"


def git(*args, check=True):
    result = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                            encoding="utf-8", errors="replace")
    if check and result.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} 실패: {result.stderr.strip()}")
    return result.stdout.strip()


def show():
    name = git("config", "--get", "agent.name", check=False) or "(없음)"
    hooks = git("config", "--get", "core.hooksPath", check=False) or "(없음)"
    terms = (ROOT / ".confidential-terms").exists()
    print(f"작업 폴더      : {ROOT}")
    print(f"agent.name     : {name}")
    print(f"core.hooksPath : {hooks}  (정상: tools/hooks)")
    print(f".confidential-terms : {'있음' if terms else '없음 — 저장소 관리자에게 비공개 경로로 받아 이 폴더 맨 위에 둔다'}")
    return name != "(없음)" and hooks == "tools/hooks" and terms


def make_labels(name):
    for label, color, desc in ((f"from:{name}", "7F77DD", f"{name}이 쓴 글"),
                               (f"to:{name}", "534AB7", f"{name}이 답해야 함")):
        result = subprocess.run(["gh", "label", "create", label, "--repo", REPO, "--color", color,
                                 "--description", desc, "--force"], capture_output=True, text=True)
        print(f"라벨 {label}: {'완료' if result.returncode == 0 else '실패 — ' + result.stderr.strip()}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("name", nargs="?", help="에이전트 이름 (예: claude1, codex1, claude2)")
    parser.add_argument("--labels", action="store_true", help="GitHub 라벨 from:/to:<이름> 생성")
    parser.add_argument("--show", action="store_true", help="현재 설정만 출력")
    args = parser.parse_args()

    if args.show or not args.name:
        ok = show()
        return 0 if ok else 1

    name = args.name.lower()
    if not NAME_RE.match(name):
        raise SystemExit("이름은 claude1, claude2, codex1 처럼 claude/codex + 숫자여야 합니다.")

    git("config", "extensions.worktreeConfig", "true")
    git("config", "--worktree", "agent.name", name)
    git("config", "core.hooksPath", "tools/hooks")
    if args.labels:
        make_labels(name)
    print()
    ok = show()
    print()
    print("준비 완료" if ok else "준비 미완료 — 위 '없음' 항목을 채운 뒤 다시 확인하세요 (python tools/setup_agent.py --show)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
