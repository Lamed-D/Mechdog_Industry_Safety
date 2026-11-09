"""Arduino의 빌드 캐시·임시 파일·사용자 라이브러리 경로를 작업 폴더로 제한합니다."""
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


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
