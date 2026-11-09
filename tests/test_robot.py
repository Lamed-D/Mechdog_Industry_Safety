"""tests/robot/ 아래 로봇 쪽 테스트를 모읍니다.

tests/robot/ 을 패키지로 두면 discover가 `robot`이라는 이름으로 불러와 실제 robot/ 코드와 이름이 겹치므로,
__init__.py 없이 두고 여기서 `tests.robot.<모듈>`로 불러옵니다.
"""

import importlib
import os

_HERE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "robot")


def load_tests(loader, tests, pattern):
    for filename in sorted(os.listdir(_HERE)):
        if filename.startswith("test_") and filename.endswith(".py"):
            module = importlib.import_module("tests.robot." + filename[:-3])
            tests.addTests(loader.loadTestsFromModule(module))
    return tests
