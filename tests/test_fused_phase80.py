import unittest

from tools.build_fused_phase80 import patch
from tools.build_main_phase_trial import SIZE


class Phase80Tests(unittest.TestCase):
    def fixture(self):
        image = bytearray(0x200000)
        body = bytearray(SIZE)
        body[:3] = bytes.fromhex('084820')
        body[-3:] = bytes.fromhex('606860')
        body[12:15] = bytes.fromhex('c96090')
        for bank in range(1, 9):
            at = bank*65536 + 0x3000
            image[at:at+SIZE] = body
        return image

    def test_only_eight_phase_operands_and_checksum(self):
        image = self.fixture()
        result, sites = patch(image, 0x3000)
        self.assertEqual(sites, [bank*65536+0x300d for bank in range(1, 9)])
        self.assertTrue(all(result[i] == 80 and image[i] == 96 for i in sites))
        allowed = set(sites) | set(range(0xffdc, 0xffe0))
        self.assertTrue(all(i in allowed for i, (a,b) in enumerate(zip(image,result)) if a != b))

    def test_wrong_phase_or_mirror_rejected(self):
        for bank in (1, 2, 8):
            image = self.fixture()
            image[bank*65536+0x300d] = 64
            with self.assertRaises(ValueError):
                patch(image, 0x3000)

    def test_ambiguous_compare_rejected(self):
        image = self.fixture()
        image[0x13020:0x13023] = bytes.fromhex('c96090')
        with self.assertRaises(ValueError):
            patch(image, 0x3000)

    def test_invalid_image_or_address_rejected(self):
        for image, address in ((b'', 0x3000), (self.fixture(), 0x2000)):
            with self.assertRaises(ValueError):
                patch(image, address)
