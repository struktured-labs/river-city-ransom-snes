import unittest
import numpy as np

from tools.audit_native_menu_boot import onset


class IdentOnsetTests(unittest.TestCase):
    def test_physical_requires_silent_reveal(self):
        pcm = np.zeros((480000, 2), dtype=np.int16)
        pcm[:48000] = 1000
        pcm[240000:288000] = 1000
        self.assertEqual(onset(pcm, 48000, True), 5)
        pcm[48000:240000] = 1000
        with self.assertRaises(ValueError):
            onset(pcm, 48000, True)

    def test_reference_uses_first_active_onset(self):
        pcm = np.zeros((320400, 2), dtype=np.int16)
        pcm[32040:64080] = 1000
        self.assertEqual(onset(pcm, 32040, False), 1)
        pcm[:32040] = 1000
        with self.assertRaises(ValueError):
            onset(pcm, 32040, False)

    def test_silence_and_truncation_rejected(self):
        for pcm in (np.zeros((480000, 2)), np.zeros((48000, 2))):
            for physical in (False, True):
                with self.assertRaises(ValueError):
                    onset(pcm, 48000, physical)
