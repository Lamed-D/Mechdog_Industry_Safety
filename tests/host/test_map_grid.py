from array import array
import math
from types import SimpleNamespace as Obj
import unittest
from host.map_review import review_edit
from ros2.map_grid import from_occupancy_grid


def message():
    return Obj(header=Obj(frame_id="map"), data=array("b", [0, -1, 100, 1]),
               info=Obj(width=2, height=2, resolution=.05,
                        origin=Obj(position=Obj(x=1., y=2., z=0.),
                                   orientation=Obj(x=0., y=0., z=0., w=1.))))


class MapGridTests(unittest.TestCase):
    def test_signed_cells_metadata_and_immutable_copy(self):
        source = message()
        grid = from_occupancy_grid(source)
        source.data[0] = 100
        self.assertEqual(grid.cells, (0, -1, 100, 1))
        self.assertEqual(grid.origin, (1., 2., 0.))
        self.assertEqual(grid.resolution, .05)

    def test_planar_rotation_and_quaternion_sign_equivalence(self):
        source = message()
        source.info.origin.orientation.z = math.sin(math.pi / 4)
        source.info.origin.orientation.w = math.cos(math.pi / 4)
        first = from_occupancy_grid(source)
        source.info.origin.orientation.z *= -1
        source.info.origin.orientation.w *= -1
        second = from_occupancy_grid(source)
        self.assertAlmostEqual(first.origin[2], math.pi / 2)
        self.assertEqual(first.digest(), second.digest())

    def test_unknown_remains_blocked_in_existing_review(self):
        base = from_occupancy_grid(message())
        proposed = message()
        proposed.data[1] = 0
        with self.assertRaisesRegex(ValueError, "unknown"):
            review_edit(base, from_occupancy_grid(proposed))

    def test_bad_pose_and_nonplanar_maps_are_rejected(self):
        for target, field, value in (("position", "z", .1), ("orientation", "x", .1),
                ("orientation", "w", 0), ("orientation", "z", float("nan")),
                ("position", "x", True), ("position", "x", 10 ** 1000)):
            with self.subTest(target=target, field=field):
                source = message()
                setattr(getattr(source.info.origin, target), field, value)
                with self.assertRaises(ValueError):
                    from_occupancy_grid(source)
        source = message()
        source.info.origin.orientation.x = .1
        source.info.origin.orientation.w = math.sqrt(.99)  # 정규화돼 있어도 평면은 아님
        with self.assertRaisesRegex(ValueError, "planar"):
            from_occupancy_grid(source)

    def test_invalid_dimensions_data_and_missing_attributes(self):
        for field, value in (("width", True), ("height", 0), ("width", 1_000_001),
                             ("resolution", 0), ("resolution", 10 ** 1000)):
            source = message()
            setattr(source.info, field, value)
            with self.subTest(field=field), self.assertRaises(ValueError):
                from_occupancy_grid(source)
        for data in ([0], [255, 0, 0, 0], [True, 0, 0, 0], b"0000", iter([0] * 4)):
            source = message()
            source.data = data
            with self.subTest(data_type=type(data).__name__), self.assertRaises(ValueError):
                from_occupancy_grid(source)
        with self.assertRaises(ValueError):
            from_occupancy_grid(Obj())
