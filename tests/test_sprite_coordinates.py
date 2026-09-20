import inspect
import unittest
from tools.build_native import build
from tools.check_sprite_coordinates import binary_expected,inputs


class SpriteCoordinatesTests(unittest.TestCase):
    def test_default_off(self):
        self.assertFalse(inspect.signature(build).parameters['experimental_sprite_coordinates'].default)

    def test_low_pair_matrix(self):
        rows=inputs(0,65536)
        self.assertEqual(len({(r[0],r[4]) for r in rows}),65536)
        self.assertEqual(sum(bool(r[12]&8) for r in rows),32768)

    def test_last_add_sets_overflow_and_cpx_sets_nzc(self):
        row=bytes((255,255,255,127,1,0,1,0,18,52,86,120,0x30,0,0,0))
        got=binary_expected(row,0xc4)
        self.assertEqual(got[:4],bytes.fromhex('00000080'))
        self.assertEqual(got[8:16],bytes((128,52,4,120,0x73,255,1,0xc4)))
        with self.assertRaises(ValueError):binary_expected(row[:12]+bytes([0x38])+row[13:],0xc4)
