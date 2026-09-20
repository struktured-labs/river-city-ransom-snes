import unittest

import numpy as np

from tools.review_wub_hardware import physical_onset


class WubHardwareAnchorTests(unittest.TestCase):
    def test_late_boot_and_first_onset(self):
        pcm = np.zeros((25000, 2), dtype=np.int16)
        pcm[14740:15000] = 100
        pcm[21550:22000] = 100
        self.assertEqual(physical_onset(pcm, 1000), 14.74)

    def test_no_silent_reveal_rejected(self):
        with self.assertRaises(ValueError):
            physical_onset(np.full((25000, 2), 100, dtype=np.int16), 1000)

    def test_missing_sound_rejected(self):
        with self.assertRaises(ValueError):
            physical_onset(np.zeros((25000, 2), dtype=np.int16), 1000)
