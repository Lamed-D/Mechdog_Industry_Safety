"""tests/scenario/ 아래 시나리오 테스트를 모읍니다.

tests/scenario/ 를 패키지로 두면 discover가 `scenario`라는 이름으로 불러와 실제 scenario/ 코드와 이름이 겹치므로,
__init__.py 없이 두고 여기서 `tests.scenario.<모듈>`로 불러옵니다.
"""

import importlib
import os

_HERE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scenario")


def load_tests(loader, tests, pattern):
    for filename in sorted(os.listdir(_HERE)):
        if filename.startswith("test_") and filename.endswith(".py"):
            module = importlib.import_module("tests.scenario." + filename[:-3])
            tests.addTests(loader.loadTestsFromModule(module))
    return tests
