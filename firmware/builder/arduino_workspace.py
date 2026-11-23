"""Arduino의 빌드 캐시·임시 파일·사용자 라이브러리 경로를 작업 폴더로 제한합니다."""
import json
import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def find_cli(override=None):
    """명령줄, 환경 변수, PATH, Arduino IDE 설치 폴더 순서로 찾습니다."""
    configured = override or os.environ.get("ARDUINO_CLI")
    if configured:
        path = Path(configured).expanduser()
        if path.is_file():
            return path.resolve()
        option = "--arduino-cli" if override else "ARDUINO_CLI"
        raise ValueError(f"{option}에 지정한 Arduino CLI 파일을 찾을 수 없습니다: {path}")

    executable = shutil.which("arduino-cli")
    if executable:
        return Path(executable).resolve()

    relative = Path("Arduino IDE/resources/app/lib/backend/resources/arduino-cli.exe")
    local = os.environ.get("LOCALAPPDATA")
    install_dirs = [Path(local) / "Programs"] if local else []
    install_dirs += [Path(os.environ.get("ProgramFiles", "C:/Program Files"))]
    for folder in install_dirs:
        candidate = folder / relative
        if candidate.is_file():
            return candidate.resolve()

    raise ValueError("arduino-cli를 찾지 못했습니다. --arduino-cli 또는 ARDUINO_CLI에 실행 파일 경로를 "
                     "지정하거나, 실행 파일이 있는 폴더를 사용자 PATH에 추가하세요.")


def configuration():
    build = ROOT / "build"
    if not build.resolve().is_relative_to(ROOT.resolve()):
        raise ValueError("build directory outside workspace")
    build.mkdir(exist_ok=True)
    data = Path(os.environ["LOCALAPPDATA"]) / "Arduino15"
    config = {"directories": {"data": str(data), "downloads": str(data / "staging"),
        "user": str(build / "arduino-user")}, "build_cache": {"path": str(build / "arduino-cache")}}
    output = build / "arduino-cli.yaml"
    output.write_text(json.dumps(config, indent=2), encoding="utf-8")
    temporary = build / "tool-tmp"
    temporary.mkdir(exist_ok=True)
    env = {**os.environ, "TMP": str(temporary), "TEMP": str(temporary)}
    return output, env
