"""비전 모듈 맞춤 펌웨어 빌드·배포 이미지 만들기 (PC에서 실행, 장치에 쓰지 않음).

    python tools/build_vision_cam.py            # 컴파일만 (build/vision_cam)
    python tools/build_vision_cam.py --release  # + build/vision_cam/latest에 최신 합본·해시·설정 기록

--release 는 firmware/vision_cam/secrets.h 가 있으면 멈춥니다. 배포하는 bin 에
Wi-Fi 비밀번호가 들어가지 않게 하기 위해서입니다(설정은 장치에서 USB 시리얼 명령으로 합니다).
"""
import argparse
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys

try:
    from .arduino_workspace import configuration
except ImportError:
    from arduino_workspace import configuration

ROOT = pathlib.Path(__file__).resolve().parent.parent
SKETCH = ROOT / "firmware" / "vision_cam"
BUILD = ROOT / "build" / "vision_cam"
COMPILE = BUILD / "compile"
RELEASE = BUILD / "latest"
# 근거: docs/vision-cam-firmware.md 3절(제조사 기본 영상 펌웨어와 같은 DIO·80MHz·4MB, 옥탈 PSRAM)
FQBN = ("esp32:esp32:esp32s3:PSRAM=opi,FlashMode=dio,FlashSize=4M,"
        "PartitionScheme=huge_app,CDCOnBoot=default,CPUFreq=240")
LOCAL = pathlib.Path(os.environ.get("LOCALAPPDATA", ""))
CLI_DEFAULT = LOCAL / "Programs" / "Arduino IDE" / "resources" / "app" / "lib" / "backend" / "resources" / "arduino-cli.exe"
ESPTOOL_GLOB = "Arduino15/packages/esp32/tools/esptool_py/*/esptool*"
REQUIRED_CORE = "3.3.12"


def source_manifest():
    if (SKETCH / "secrets.h").exists():
        sys.exit("secrets.h 가 있어 배포 소스 검사를 중단합니다.")
    paths = [path for path in SKETCH.rglob("*") if path.suffix in (".ino", ".h", ".c", ".cpp")]
    paths += [ROOT / "tools/build_vision_cam.py", ROOT / "tools/arduino_workspace.py"]
    files = {path.relative_to(ROOT).as_posix(): hashlib.sha256(
        path.read_text(encoding="utf-8").encode("utf-8")).hexdigest() for path in sorted(paths)}
    encoded = json.dumps(files, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {"source_sha256": hashlib.sha256(encoded).hexdigest(), "source_files": files}


def compiled_core_version():
    options = json.loads((COMPILE / "build.options.json").read_text(encoding="utf-8"))
    versions = set()
    for folder in options.get("hardwareFolders", "").split(","):
        match = re.search(r"[/\\]esp32[/\\]hardware[/\\]esp32[/\\]([0-9.]+)$", folder)
        if match:
            versions.add(match.group(1))
    if versions != {REQUIRED_CORE}:
        sys.exit("컴파일 코어가 요구 버전과 다릅니다. 배포를 중단합니다.")
    return REQUIRED_CORE


def verify_release():
    manifest = json.loads((RELEASE / "manifest.json").read_text(encoding="utf-8"))
    data = (RELEASE / "mechdog_vision_cam_0x0.bin").read_bytes()
    checksum = (RELEASE / "mechdog_vision_cam_0x0.sha256").read_text(encoding="ascii").strip()
    binary_sha = hashlib.sha256(data).hexdigest()
    sources = source_manifest()
    if (any(manifest.get(key) != value for key, value in sources.items())
            or manifest.get("version") != version() or manifest.get("fqbn") != FQBN
            or manifest.get("core_version") != REQUIRED_CORE
            or manifest.get("profile") not in ("balanced", "detail")
            or manifest.get("merged_bytes") != len(data)
            or manifest.get("sha256") != binary_sha
            or checksum != binary_sha + "  mechdog_vision_cam_0x0.bin"):
        raise ValueError("release does not match current sources or binary")
    return manifest


def find_tool(env, default, pattern):
    if os.environ.get(env):
        return pathlib.Path(os.environ[env])
    if default and default.exists():
        return default
    found = sorted(LOCAL.glob(pattern)) if pattern else []
    if found:
        return found[-1]
    name = shutil.which(env.lower().replace("_path", ""))
    if name:
        return pathlib.Path(name)
    sys.exit("%s 를 찾지 못했습니다. 환경 변수 %s 로 경로를 알려 주세요." % (env, env))


def version():
    text = (SKETCH / "config.h").read_text(encoding="utf-8")
    return re.search(r'#define CAM_FW_VERSION "([0-9.]+)"', text).group(1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--release", action="store_true")
    parser.add_argument("--profile", choices=("balanced", "detail"), default="balanced")
    parser.add_argument("--verify-release", action="store_true", help="최신 합본·소스·설정만 읽어 검사")
    args = parser.parse_args()
    if args.verify_release:
        manifest = verify_release()
        print("verified release %s %s; hardware remains unverified" % (manifest["version"], manifest["profile"]))
        return
    if not BUILD.resolve().is_relative_to(ROOT.resolve()):
        sys.exit("빌드 경로가 작업 폴더 밖입니다.")
    if args.release and (SKETCH / "secrets.h").exists():
        sys.exit("secrets.h 가 있어 배포 이미지를 만들지 않습니다. 잠시 다른 곳으로 옮긴 뒤 다시 실행하세요.")
    sources = source_manifest() if args.release else None

    cli = find_tool("ARDUINO_CLI", CLI_DEFAULT, None)
    tool_config, tool_env = configuration()
    # 이미지 안의 소스 경로(__FILE__)에서 이 PC의 사용자 폴더를 지웁니다.
    remap = "-fmacro-prefix-map=%s=/arduino15 -fmacro-prefix-map=%s=/src" % (LOCAL / "Arduino15", ROOT)
    remap += " -DCAM_VIDEO_PROFILE=%d" % (1 if args.profile == "balanced" else 2)
    props = ["--build-property", "compiler.c.extra_flags=" + remap,
             "--build-property", "compiler.cpp.extra_flags=" + remap]
    subprocess.run([str(cli), "--config-file", str(tool_config), "compile", "--fqbn", FQBN, "--build-path", str(COMPILE),
                    "--warnings", "all", *props, str(SKETCH)], check=True, env=tool_env)
    app = COMPILE / "vision_cam.ino.bin"
    print("app %s: %d bytes" % (app.name, app.stat().st_size))
    if not args.release:
        return
    core_version = compiled_core_version()
    if sources != source_manifest():
        sys.exit("컴파일 중 소스가 바뀌어 배포를 중단합니다.")

    esptool = find_tool("ESPTOOL_PATH", None, ESPTOOL_GLOB)
    boot_app0 = sorted(LOCAL.glob("Arduino15/packages/esp32/hardware/esp32/*/tools/partitions/boot_app0.bin"))[-1]
    staging = BUILD / "release-pending"
    staging.mkdir(exist_ok=True)
    out = staging / "mechdog_vision_cam_0x0.bin"
    # 부트로더 0x0, 파티션 표 0x8000, OTA 선택 0xe000, 앱 0x10000 을 한 파일로(빈 영역은 채우지 않음)
    subprocess.run([str(esptool), "--chip", "esp32s3", "merge-bin", "-o", str(out),
                    "--flash-mode", "dio", "--flash-freq", "80m", "--flash-size", "4MB",
                    "0x0", str(COMPILE / "vision_cam.ino.bootloader.bin"),
                    "0x8000", str(COMPILE / "vision_cam.ino.partitions.bin"),
                    "0xe000", str(boot_app0),
                    "0x10000", str(app)], check=True, env=tool_env)
    data = out.read_bytes()
    for marker in (b"\\Users\\", b"/Users/"):  # 이 PC 경로가 남았는지
        if marker in data:
            sys.exit("이미지에 로컬 사용자 경로가 있어 배포를 중단합니다.")
    digest = hashlib.sha256(data).hexdigest()
    if sources != source_manifest():
        sys.exit("합본 생성 중 소스가 바뀌어 배포를 중단합니다.")
    (out.with_suffix(".sha256")).write_text("%s  %s\n" % (digest, out.name), encoding="ascii")
    (staging / "manifest.json").write_text(json.dumps({"version": version(), "fqbn": FQBN,
        "app_bytes": app.stat().st_size, "merged_bytes": len(data), "sha256": digest,
        "profile": args.profile, "core_version": core_version, **sources,
        "hardware_verified": False}, indent=2) + "\n", encoding="utf-8")
    # 성공한 합본만 최신으로 교체합니다. 삭제 대상은 이 작업 폴더 build 하위로 제한합니다.
    for target in (RELEASE, staging):
        if not target.resolve().is_relative_to(BUILD.resolve()):
            sys.exit("빌드 정리 대상이 build 밖입니다.")
    if RELEASE.exists():
        shutil.rmtree(RELEASE)
    staging.rename(RELEASE)
    print("release %s: %d bytes, sha256 %s" % (out.name, len(data), digest))


if __name__ == "__main__":
    main()
