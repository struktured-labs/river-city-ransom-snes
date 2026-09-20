"""Objective pitch measurement independently rejects wrong notes."""
import unittest

import numpy as np

from tools.audit_ident_audio import GLIDE_CHECKPOINTS, frequency
from tools.build_ident_spc import curve


class IdentPitchTests(unittest.TestCase):
    def test_low_sub_and_upper_octave_fundamentals(self):
        rate = 16000
        time = np.arange(0, 0.10, 1/rate)
        for target in (110, 131, 220, 311, 622):
            with self.subTest(hz=target):
                samples = 1000 * np.sin(2 * np.pi * target * time)
                self.assertLess(abs(frequency(samples, rate, target) / target - 1), 0.015)

    def test_wrong_sustained_note_cannot_satisfy_target(self):
        rate = 16000
        time = np.arange(0, 0.10, 1/rate)
        actual = 276
        samples = np.sin(2 * np.pi * actual * time)
        target = int.from_bytes(curve()[:2], 'little') * 1000 / 4096
        measured = frequency(samples, rate, target)
        self.assertGreater(abs(measured / target - 1), 0.015)

    def test_glide_checkpoints_cover_start_middle_and_low_wobble(self):
        self.assertEqual(len(GLIDE_CHECKPOINTS), 12)
        self.assertLess(GLIDE_CHECKPOINTS[0], 16)
        self.assertGreater(GLIDE_CHECKPOINTS[-1], 190)


if __name__ == '__main__':
    unittest.main()
