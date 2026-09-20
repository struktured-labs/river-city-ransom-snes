import unittest
from tools.build_sprite_copy_prepare import patch, PREIMAGE, REPLACEMENT


class SpriteCopyPrepareTests(unittest.TestCase):
    def test_exact_hooks_and_occupied_slot_rejection(self):
        data = bytearray(b'\xff'*0x200000)
        for bank in range(1, 9): data[bank*65536+0x2771:bank*65536+0x277a] = PREIMAGE
        result = patch(data, bytes(256), 0x2771)
        self.assertEqual(result[0x7800:0x7900], bytes(256))
        for bank in range(1, 9):
            self.assertEqual(result[bank*65536+0x2771:bank*65536+0x277a], REPLACEMENT)
        data[0x7800] = 0
        with self.assertRaises(ValueError): patch(data, bytes(256), 0x2771)
        data[0x7800] = 255; data[0x82771] ^= 1
        with self.assertRaises(ValueError): patch(data, bytes(256), 0x2771)
