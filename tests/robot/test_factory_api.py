"""실물 본체처럼 MechDog·MPU 가 '객체를 돌려주는 함수'일 때 bringup 점검이 오탐하지 않는지 봅니다.

로봇 B 실물(2026-11-10): type(MechDog) 는 function, dir 은 __class__·__name__·__globals__ 뿐,
Hiwonder_IIC.MPU(IIC(1)) 는 TypeError(인자 0개), MPU().read_angle() 은 각도 두 개.
"""

import contextlib
import io
import unittest

from tests import fakes
from tests.fakes.fake_time import FakeClock
from tests.robot.test_bringup import load


def mechdog_factory():
    """실물처럼 클래스가 아닌 함수. 호출하면 가짜 MechDog 객체를 돌려줍니다."""
    return fakes.HW_MechDog.MechDog()


class NoArgIIC:
    """실물처럼 MPU 가 인자를 받지 않는 IIC 모듈."""

    def __init__(self):
        self.mpu_args = []

    def IIC(self, bus):
        return object()

    def MPU(self, *args):
        self.mpu_args.append(args)
        if args:
            raise TypeError("function takes 0 positional arguments but 1 were given")
        return fakes.Hiwonder_IIC.MPU()


class FactoryApiTests(unittest.TestCase):
    def setUp(self):
        fakes.install()
        self.addCleanup(fakes.uninstall)
        quiet = contextlib.redirect_stdout(io.StringIO())
        quiet.__enter__()
        self.addCleanup(quiet.__exit__, None, None, None)

    def test_mechdog_only_reports_factory_as_unchecked_not_missing(self):
        result = load("mechdog_only").inspect(fakes.Hiwonder, mechdog_factory)
        self.assertEqual(result["mechdog_kind"], "factory")
        self.assertTrue(all(value is None for value in result["api"].values()))
        self.assertEqual(result["battery_mv"], 7800)
        self.assertEqual(fakes.HW_MechDog.instances, [])

    def test_mechdog_only_still_checks_a_real_class(self):
        result = load("mechdog_only").inspect(fakes.Hiwonder, fakes.HW_MechDog.MechDog)
        self.assertEqual(result["mechdog_kind"], "class")
        self.assertTrue(all(value is True for value in result["api"].values()))

    def test_api_candidates_factory_is_unchecked_and_never_constructed(self):
        result = load("api_candidates").inspect(mechdog_factory)
        self.assertTrue(all(value is None for value in result.values()))
        self.assertEqual(fakes.HW_MechDog.instances, [])

    def test_imu_uses_argumentless_mpu_like_the_device(self):
        api = NoArgIIC()
        result = load("robot_imu_check").run(api, FakeClock())
        self.assertEqual(result["status"], "read")
        self.assertEqual(api.mpu_args, [()])

    def test_motion_check_accepts_factory_and_still_stops(self):
        probe = load("robot_motion_check")
        result = probe.run("stop", True, fakes.Hiwonder, mechdog_factory, FakeClock())
        self.assertEqual(result["status"], "calls_completed")
        dog = fakes.HW_MechDog.instances[-1]
        self.assertEqual(dog.last_move, (0, 0))
        self.assertEqual(len(dog.fake_calls("stop_action")), 2)

    def test_move_ms_is_bounded_and_still_stops(self):
        probe = load("robot_motion_check")
        clock = FakeClock()
        result = probe.run("forward", True, fakes.Hiwonder, mechdog_factory, clock, move_ms=10000)
        self.assertEqual(result["status"], "calls_completed")
        self.assertEqual(fakes.HW_MechDog.instances[-1].last_move, (0, 0))
        count = len(fakes.HW_MechDog.instances)
        for bad in (0, -1, 10001, 1.5, True, "1000"):
            with self.assertRaises(ValueError):
                probe.run("forward", True, fakes.Hiwonder, mechdog_factory, clock, move_ms=bad)
        self.assertEqual(len(fakes.HW_MechDog.instances), count)

    def test_factory_object_without_methods_fails_before_any_motion_call(self):
        class Bare:
            pass

        probe = load("robot_motion_check")
        result = probe.run("forward", True, fakes.Hiwonder, lambda: Bare(), FakeClock())
        self.assertEqual(result["status"], "unknown")
        self.assertEqual(result["reason"], "required_api_missing")
        self.assertEqual(result["stage"], "construct")

    def test_motion_check_with_missing_factory_never_constructs(self):
        probe = load("robot_motion_check")
        not_callable = object()
        result = probe.run("forward", True, fakes.Hiwonder, not_callable, FakeClock())
        self.assertEqual(result["reason"], "required_api_missing")
        self.assertEqual(fakes.HW_MechDog.instances, [])


if __name__ == "__main__":
    unittest.main()
