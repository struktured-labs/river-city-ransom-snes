import unittest

from tools.check_sprite_position import inputs, binary_expected, fixture, PREIMAGE


class SpritePositionTests(unittest.TestCase):
    def test_independent_binary_signed_offsets(self):
        row=bytes((0x80,0xff,0,1,0,1,0,0xff,0,0x5a,0,0,0x30,0,0,0))
        got=binary_expected(row,0x84)
        self.assertEqual(len(got),32)
        self.assertEqual(got[:4],bytes.fromhex('8000ff00'))
        self.assertEqual(got[8:12],bytes((0,0x5a,4,0xff)))
        flipped=bytearray(row);flipped[6]=1
        self.assertEqual(binary_expected(flipped,0x84)[:2],bytes.fromhex('7f01'))

    def test_fixture_binds_complete_original_block(self):
        text=fixture()
        self.assertIn('jsr $EEEE',text)
        self.assertNotIn('jsr $EF11',text)
        self.assertEqual(len(PREIMAGE),56)
        self.assertIn('.res 53,$EA',text)
        self.assertIn('sprite_position.inc',text)

    def test_matrix_and_decimal_scope(self):
        rows=inputs(0,65536)
        self.assertEqual(len({r[:2] for r in rows}),65536)
        self.assertEqual(sum(not r[12]&8 for r in rows),32768)
        with self.assertRaises(ValueError):binary_expected(rows[1],0x81)
