import struct
import unittest
import numpy as np

from tools.brand_title import LABEL, OFFSET, ORIGINAL, encode, patch
from tools.check_title_branding import visual_gates


def image():
    data = bytearray(0x200000)
    data[0xFFC0:0xFFD5] = b'RCR NATIVE CPU PROOF '
    data[OFFSET:OFFSET + len(ORIGINAL)] = ORIGINAL
    data[0xFFDC:0xFFE0] = b'\xff\xff\0\0'
    checksum = sum(data) & 0xFFFF
    struct.pack_into('<HH', data, 0xFFDC, checksum ^ 0xFFFF, checksum)
    return bytes(data)


class TitleBrandingTests(unittest.TestCase):
    def test_only_footer_and_checksum_change(self):
        before = image()
        after = patch(before)
        allowed = set(range(OFFSET, OFFSET + 29)) | set(range(0xFFDC, 0xFFE0))
        self.assertTrue(all(a == b or i in allowed for i, (a, b) in enumerate(zip(before, after))))
        self.assertEqual(after[OFFSET:OFFSET + 29], encode(LABEL))
        self.assertEqual(len(after), len(before))
        self.assertEqual(sum(after) & 0xFFFF, struct.unpack_from('<H', after, 0xFFDE)[0])

    def test_reject_bad_or_already_branded_image(self):
        with self.assertRaises(ValueError):
            patch(patch(image()))
        damaged = bytearray(image())
        damaged[OFFSET] ^= 1
        with self.assertRaises(ValueError):
            patch(damaged)
        with self.assertRaises(ValueError):
            patch(image()[:-1])

    def test_font_mapping(self):
        self.assertEqual(encode('AZ .'), bytes((0xC0, 0xD9, 0, 0xB6)))
        with self.assertRaises(ValueError):
            encode('!')

    def test_visual_oracle_rejects_blank_wrong_glyph_and_outside_change(self):
        a = np.zeros((239, 256, 3), dtype=np.uint8)
        expected = np.zeros((8, 232), dtype=bool)
        expected[0, 0] = True
        b = a.copy()
        b[200, 16] = 255
        self.assertTrue(all(visual_gates(a, b, expected).values()))
        self.assertFalse(visual_gates(a, a, expected)['original_font_exact'])
        bad = b.copy()
        bad[200, 17] = 255
        self.assertFalse(visual_gates(a, bad, expected)['original_font_exact'])
        bad = b.copy()
        bad[0, 0] = 255
        self.assertFalse(visual_gates(a, bad, expected)['only_footer_pixels_changed'])
