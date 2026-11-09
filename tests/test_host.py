"""Discover host tests without shadowing the production host package."""

import importlib
from pathlib import Path


def load_tests(loader, tests, pattern):
    for path in sorted((Path(__file__).parent / "host").glob("test_*.py")):
        tests.addTests(loader.loadTestsFromModule(importlib.import_module("tests.host." + path.stem)))
    return tests
