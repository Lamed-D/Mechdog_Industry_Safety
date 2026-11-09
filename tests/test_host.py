"""Discover host tests without shadowing the production host package."""

from tests.host import test_lidar


def load_tests(loader, tests, pattern):
    return loader.loadTestsFromModule(test_lidar)
