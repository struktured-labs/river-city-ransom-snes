import unittest

from tools.audit_duty_audio import near_zero_run


class DutyAudioTests(unittest.TestCase):
    def test_exact_gap_and_boundaries(self):
        self.assertEqual(near_zero_run([0]*5 + [100, -100]), 5)
        self.assertEqual(near_zero_run([100, -100] + [0]*5), 5)
        self.assertEqual(near_zero_run([100, 0, 0, 100, 0]), 2)

    def test_threshold_is_strict(self):
        self.assertEqual(near_zero_run([-8, 8]), 0)
        self.assertEqual(near_zero_run([-7, 7]), 2)

    def test_silence_is_not_a_quality_pass(self):
        self.assertEqual(near_zero_run([0]*600), 600)
        self.assertEqual(near_zero_run([]), 0)

    def test_stereo_requires_explicit_channel(self):
        with self.assertRaises(ValueError):
            near_zero_run([[0, 0]])
