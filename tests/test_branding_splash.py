import struct
import unittest

import numpy as np
from PIL import Image

from tools.build_branding_splash import encode, patch


def native_image():
    data = bytearray(b'\xff' * 0x200000)
    data[0x8000:0x8005] = bytes.fromhex('7818fbc238')
    data[0xFFDC:0xFFE0] = b'\xff\xff\0\0'
    checksum = sum(data) & 0xFFFF
    struct.pack_into('<HH', data, 0xFFDC, checksum ^ 0xFFFF, checksum)
    return bytes(data)


class SplashTests(unittest.TestCase):
    def test_planar_tile_palette_roundtrip(self):
        y, x = np.indices((239, 256))
        rgb = np.stack(((x % 8) * 32, (y % 8) * 32, ((x + y) % 8) * 32), axis=-1).astype(np.uint8)
        tiles, tilemap, palette, preview = encode(Image.fromarray(rgb))
        actual = np.zeros((239, 256, 3), dtype=np.uint8)
        colors = struct.unpack('<256H', palette)
        for yy in range(239):
            for xx in range(256):
                tile = struct.unpack_from('<H', tilemap, ((yy//8)*32+xx//8)*2)[0]
                index = 0
                for bit in range(8):
                    byte = tiles[tile*64 + (bit//2)*16 + (yy%8)*2 + bit%2]
                    index |= ((byte >> (7-xx%8)) & 1) << bit
                c = colors[index]
                actual[yy, xx] = (c & 31, (c >> 5) & 31, (c >> 10) & 31)
        np.testing.assert_array_equal(actual, np.asarray(preview) >> 3)

    def test_patch_changes_only_reset_spare_bank_and_checksum(self):
        before = native_image()
        after = patch(before, bytes(0x10000))
        self.assertEqual(after[0x8005:0xFFDC], before[0x8005:0xFFDC])
        self.assertEqual(after[0xFFE0:0x110000], before[0xFFE0:0x110000])
        self.assertEqual(after[0x120000:], before[0x120000:])
        self.assertEqual(after[0x8000:0x8005], bytes.fromhex('5c0000d1ea'))
        self.assertEqual(sum(after) & 0xFFFF, struct.unpack_from('<H', after, 0xFFDE)[0])

    def test_patch_rejects_occupied_bank_and_duplicate_application(self):
        before = bytearray(native_image())
        before[0x110000] = 0
        with self.assertRaises(ValueError):
            patch(before, bytes(0x10000))
        with self.assertRaises(ValueError):
            patch(patch(native_image(), bytes(0x10000)), bytes(0x10000))
