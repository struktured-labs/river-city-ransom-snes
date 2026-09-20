import unittest
import numpy as np

from tools.review_native_command_gaps import align, onset


class NativeCommandGapTests(unittest.TestCase):
    def test_bound_lag_and_fixed_holdout(self):
        rng = np.random.default_rng(710)
        predicted = rng.normal(size=11000)
        actual = np.r_[np.zeros(300), predicted, np.zeros(1000)]
        result = align(actual, predicted, .602)
        self.assertEqual(result['offset_bins'], 300)
        self.assertAlmostEqual(result['training_correlation'], 1)
        self.assertEqual(len(result['scores']), 41)
        actual[5000:5500] = 0  # held out; cannot change calibration
        self.assertEqual(align(actual, predicted, .602), result)

    def test_silence_cannot_anchor_or_fit(self):
        with self.assertRaises(ValueError):
            onset(np.zeros((1000, 2), dtype=np.int16), 48000)
        with self.assertRaises(ValueError):
            align(np.zeros(10000), np.zeros(8000), .1)

    def test_repeat_phrase_cannot_move_to_later_occurrence(self):
        rng = np.random.default_rng(511)
        predicted = rng.normal(size=4000)
        actual = np.r_[np.zeros(200), predicted+rng.normal(0, .1, 4000), np.zeros(200), predicted]
        self.assertEqual(align(actual, predicted, .4)['offset_bins'], 200)
