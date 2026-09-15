import struct
import unittest
from tools.check_rows import expected_rows


class RowOracleTests(unittest.TestCase):
    def test_four_quadrants_and_pattern_half(self):
        shadow = bytearray(4096)
        shadow[:960] = bytes([5])*960
        shadow[960] = 0xE4
        result = expected_rows(shadow, 16)
        for x, y, palette in ((0, 0, 0), (2, 0, 1), (0, 2, 2), (2, 2, 3)):
            self.assertEqual(struct.unpack_from('<H', result, (y*32+x)*2)[0], 261+palette*1024)
        self.assertEqual(result[1920:2048], bytes(128))

    def test_invalid_geometry_and_half_rejected(self):
        for shadow, half in ((bytes(4095), 0), (bytes(4096), 8)):
            with self.assertRaises(ValueError): expected_rows(shadow, half)
