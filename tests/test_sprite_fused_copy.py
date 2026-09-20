import unittest
from tools.build_sprite_fused_copy import patch, copy_pattern, SIZE, POST


class FusedSpriteCopyTests(unittest.TestCase):
    def sample(self):
        data=bytearray(b'\xff'*0x200000);old=bytes(range(256));data[0x7800:0x7900]=old
        for bank in range(1,9):
            at=bank*65536+0x2400
            data[at-2:at]=bytes.fromhex('eb5b');data[at:at+768]=copy_pattern()
            data[bank*65536+0x2771:bank*65536+0x277a]=bytes.fromhex('220078c0eaeaeaeaea')
        return data,old

    def test_exact_copies_and_fallback_relocation(self):
        data,old=self.sample();result,sites=patch(data,bytes(SIZE),0x2771,old)
        self.assertEqual(len(sites),8)
        self.assertEqual(result[0x7900:0x7a00],old)
        self.assertEqual(result[0x7800:0x7800+len(POST)],POST)
        self.assertEqual(POST[2+POST[1]:],bytes.fromhex('5c0079c0'))
        for at in sites:self.assertEqual(result[at:at+7],bytes.fromhex('220020c04c7127'))

    def test_changed_hooks_or_occupied_space_rejected(self):
        for at in (0x2000,0x7900,0x82771,0x123ff):
            data,old=self.sample();data[at]^=1
            with self.assertRaises(ValueError):patch(data,bytes(SIZE),0x2771,old)
