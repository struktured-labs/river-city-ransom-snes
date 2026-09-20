import unittest
from tools.check_render_regression import fixed_samples


class RenderRegressionTests(unittest.TestCase):
    def setUp(self):
        self.row = dict(room=3, camera=240, nes_frame=7604, snes_frame=8670,
                        background_playfield_differences=6849)
        self.old = dict(comparisons=[self.row])

    def test_exact_frame_match_keeps_new_failure_or_success(self):
        for differences in (0, 6849):
            new = dict(self.row, background_playfield_differences=differences)
            self.assertEqual(fixed_samples(self.old, dict(comparisons=[new])), [(self.row, new)])

    def test_missing_duplicate_and_empty_samples_rejected(self):
        for rows in ([], [self.row, self.row]):
            with self.assertRaises(ValueError):
                fixed_samples(self.old, dict(comparisons=rows))
        with self.assertRaisesRegex(ValueError, 'No previous'):
            fixed_samples(dict(comparisons=[]), self.old)

    def test_frame_rematching_rejected(self):
        for key in ('nes_frame', 'snes_frame'):
            new = dict(self.row)
            new[key] += 1
            with self.assertRaisesRegex(ValueError, 'frame changed'):
                fixed_samples(self.old, dict(comparisons=[new]))
