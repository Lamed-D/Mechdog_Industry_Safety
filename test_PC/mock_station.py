"""Start one operator's console, robot, camera, and LiDAR on loopback."""

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--robot", choices=("A", "B"), required=True)
    robot = parser.parse_args().robot
    root = Path(__file__).resolve().parents[1]
    frame = Path("dashboard/mock_frame.jpg")
    modules = [
        ("dashboard.fake_robot", "--robot", robot),
        ("tools.mock.mock_camera", "--robot", robot, "--frame", str(frame)),
        ("tools.mock.mock_lidar",),
        ("dashboard.server", "--robot", robot,
         "--cam", "http://127.0.0.1:8081/stream", "--lidar-tcp", "127.0.0.1"),
    ]
    flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    jobs = []
    try:
        for module, *args in modules:
            job = subprocess.Popen([sys.executable, "-u", "-m", module, *args],
                                   cwd=root, creationflags=flags)
            jobs.append((module, job))
        print(f"Mock {robot}: http://127.0.0.1:8090/ (Ctrl+C to exit)", flush=True)
        while True:
            for module, job in jobs:
                if job.poll() is not None:
                    raise SystemExit(f"{module} exited with {job.returncode}")
            time.sleep(0.2)
    except KeyboardInterrupt:
        pass
    finally:
        for _, job in reversed(jobs):
            if job.poll() is None:
                job.terminate()
            job.wait()


if __name__ == "__main__":
    main()
