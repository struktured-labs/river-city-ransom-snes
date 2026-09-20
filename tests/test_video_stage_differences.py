import unittest
import numpy as np
from tools.audit_video_stage_differences import pixels


class VideoStageDifferenceTests(unittest.TestCase):
    def test_keeps_background_and_primary_populations_separate(self):
        a = np.zeros((239, 256, 3), dtype=np.uint8); b = a.copy()
        ba = np.zeros((240, 256, 3), dtype=np.uint8); bb = ba.copy()
        b[20, 4] = 32; b[30, 5] = 32; b[40, 6] = 32
        bb[30, 5] = 32; bb[50, 7] = 32
        va = bytearray([1]*240); vb = va.copy(); vb[40] = 0
        r = pixels(a, b, ba, bb, va, vb)
        self.assertEqual(r['changed_pixels'], 3)
        self.assertEqual(r['bbox'], [4, 20, 7, 41])
        self.assertEqual(r['supported_background_changed_pixels'], 2)
        for k in ('primary_changed_background_equal', 'primary_changed_background_changed',
                  'primary_changed_background_unsupported'):
            self.assertEqual(r[k], 1)
        self.assertEqual(r['unsupported_background_lines'], [40])

    def test_rejects_bad_coverage_and_preserves_no_change(self):
        a = np.zeros((239, 256, 3), dtype=np.uint8)
        bg = np.zeros((240, 256, 3), dtype=np.uint8)
        r = pixels(a, a, bg, bg, bytes(240), bytes(240))
        self.assertEqual(r['changed_pixels'], 0)
        self.assertIsNone(r['bbox'])
        self.assertEqual(len(r['unsupported_background_lines']), 239)
        for flags in (bytes(239), bytes([2]*240)):
            with self.assertRaises(ValueError):
                pixels(a, a, bg, bg, flags, bytes(240))
