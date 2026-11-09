"""로봇 코드를 PC에서 불러오기 위한 준비.

장치에서는 robot/·custom_sensors/ 파일이 모두 맨 위에 놓이므로(`import proto`, `import core`)
PC에서도 두 폴더를 sys.path 에 넣습니다. 표준 라이브러리 `secrets`가 로컬 robot/secrets.py 에
가려지지 않도록 먼저 불러 둡니다.
"""

import os
import secrets as _stdlib_secrets  # noqa: F401  (가려짐 방지)
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _folder in ("custom_sensors", "robot"):
    _path = os.path.join(ROOT, _folder)
    if _path not in sys.path:
        sys.path.insert(0, _path)

import config  # noqa: E402


class Cfg:
    """config.py 값을 복사해 테스트마다 바꿀 수 있게 한 설정."""

    def __init__(self, **overrides):
        for key in dir(config):
            if key.isupper():
                value = getattr(config, key)
                setattr(self, key, dict(value) if isinstance(value, dict) else value)
        for key, value in overrides.items():
            setattr(self, key, value)
