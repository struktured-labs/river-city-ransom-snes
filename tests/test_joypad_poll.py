import unittest

from tools.check_joypad_poll import inputs,expected,fixture,PREIMAGE,mutation_inputs


class JoypadPollTests(unittest.TestCase):
    def test_mutant_matrix_exercises_both_serial_streams(self):
        rows=mutation_inputs()
        for index in (0,1):
            self.assertEqual({r[index] for r in rows},set(range(256)))

    def test_all_cached_pad_pairs_and_variation(self):
        rows=inputs(0,65536)
        self.assertEqual(len({r[:2] for r in rows}),65536)
        self.assertEqual({r[7] for r in rows},{0,1})
        self.assertEqual({r[13] for r in rows},{0,1})
        self.assertEqual({r[12]&8 for r in rows},{0,8})

    def test_independent_bit_order_carry_and_registers(self):
        row=bytearray(inputs(0,1)[0]);row[:6]=bytes((0x81,0x40,0x33,0x66,0x55,1))
        got=expected(row,0x85)
        self.assertEqual(len(got),32)
        self.assertEqual(got[:8],bytes.fromhex('81020000ffff0000'))
        self.assertEqual(got[8:11],bytes((0,0x1b,0)))
        self.assertEqual(got[12]&0x83,3)
        self.assertEqual(got[15],0x85)

    def test_live_fallback_preserves_cached_bytes(self):
        row=inputs(0x8001,1,True)[0]
        self.assertEqual(expected(row,0x81)[:6],b'\0\0\0\0'+row[:2])

    def test_fixture_binds_original_loop_and_real_stubs(self):
        source=fixture()
        self.assertEqual(len(PREIMAGE),21)
        self.assertIn('jsr $FD8E',source)
        self.assertIn('jsr legacy1',source)
        self.assertIn('jsr legacy2',source)
        self.assertNotIn('sprite_coordinates.inc',source)
        self.assertIn('$FDA3',source)
