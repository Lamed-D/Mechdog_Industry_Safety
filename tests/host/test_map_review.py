import unittest
from host.map_review import Grid, approve_edit, review_edit


class MapReviewTests(unittest.TestCase):
    def grid(self, cells, **kwargs):
        return Grid(2, 2, 0.05, (0, 0, 0), cells, **kwargs)

    def test_immutable_copy_and_repeatable_digest(self):
        cells = [0, -1, 100, 1]
        grid = self.grid(cells)
        digest = grid.digest()
        cells[0] = 100
        self.assertEqual(grid.cells[0], 0)
        self.assertEqual(digest, grid.digest())
        self.assertEqual(digest, self.grid([0, -1, 100, 1]).digest())

    def test_unknown_to_free_forbidden_even_with_approval(self):
        base, edit = self.grid([-1, 0, 0, 0]), self.grid([0, 0, 0, 0])
        with self.assertRaisesRegex(ValueError, "unknown"):
            approve_edit(base, edit, expected_base_digest=base.digest(),
                         expected_proposal_digest=edit.digest(), approved_clearings=[0])

    def test_each_obstacle_clearing_requires_exact_approval(self):
        base, edit = self.grid([100, 1, -1, 0]), self.grid([0, 0, 100, 1])
        review = review_edit(base, edit)
        self.assertEqual(review.cleared_cells, (0, 1))
        self.assertEqual(review.changed_cells, 4)
        args = dict(expected_base_digest=base.digest(), expected_proposal_digest=edit.digest())
        for approvals in ([], [0], [0, 1, 2], [True, 0], [0.0, 1], "0,1"):
            with self.subTest(approvals=approvals), self.assertRaises(ValueError):
                approve_edit(base, edit, approved_clearings=approvals, **args)
        self.assertEqual(approve_edit(base, edit, approved_clearings=[0, 1], **args), review)

    def test_add_obstacles_or_unknown_without_clearing(self):
        base, edit = self.grid([0, -1, 100, 1]), self.grid([1, 100, -1, 1])
        review = approve_edit(base, edit, expected_base_digest=base.digest(),
                              expected_proposal_digest=edit.digest())
        self.assertEqual(review.cleared_cells, ())

    def test_geometry_and_frame_changes_are_rejected(self):
        base = self.grid([0] * 4)
        for grid in (Grid(1, 4, .05, (0, 0, 0), [0] * 4),
                     Grid(2, 2, .1, (0, 0, 0), [0] * 4),
                     Grid(2, 2, .05, (1, 0, 0), [0] * 4),
                     self.grid([0] * 4, frame="odom")):
            with self.subTest(grid=grid), self.assertRaises(ValueError):
                review_edit(base, grid)

    def test_changed_base_or_proposal_invalidates_previous_approval(self):
        base, edit = self.grid([100, 0, 0, 0]), self.grid([0] * 4)
        args = dict(expected_base_digest=base.digest(), expected_proposal_digest=edit.digest(),
                    approved_clearings=[0])
        with self.assertRaisesRegex(ValueError, "changed"):
            approve_edit(self.grid([100, 1, 0, 0]), edit, **args)
        with self.assertRaisesRegex(ValueError, "changed"):
            approve_edit(base, self.grid([0, 1, 0, 0]), **args)

    def test_invalid_and_unbounded_inputs_are_rejected(self):
        for cells in ([0] * 3, [True, 0, 0, 0], [101, 0, 0, 0], [-2, 0, 0, 0],
                      [float("nan"), 0, 0, 0], [0.0] * 4):
            with self.subTest(cells=cells), self.assertRaises(ValueError):
                self.grid(cells)
        for width, height, res, origin in ((True, 2, .05, (0, 0, 0)),
                (0, 2, .05, (0, 0, 0)), (1001, 1000, .05, (0, 0, 0)),
                (2, 2, 0, (0, 0, 0)), (2, 2, float("inf"), (0, 0, 0)),
                (2, 2, .05, (0, 0)), (2, 2, .05, (0, 0, float("nan")))):
            with self.subTest(width=width, res=res), self.assertRaises(ValueError):
                Grid(width, height, res, origin, [0] * 4)
