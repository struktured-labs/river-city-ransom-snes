import unittest

from tools.build_phase_camera_trial import BODY, patch


class PhaseCameraTests(unittest.TestCase):
    def fixture(self):
        image = bytearray(b'\xff'*0x200000)
        for bank in range(1,9):
            image[bank*65536+0x3293:bank*65536+0x3293+len(BODY)] = BODY
        return image

    def test_only_early_admission_immediates_and_checksum_change(self):
        old = self.fixture()
        new, sites = patch(old, 0x3293)
        self.assertEqual(len(set(sites)), 8)
        self.assertTrue(all(old[i] == 30 and new[i] == 0 for i in sites))
        allowed = set(sites) | set(range(0xffdc,0xffe0))
        self.assertTrue(all(i in allowed for i,(a,b) in enumerate(zip(old,new)) if a != b))
        with self.assertRaises(ValueError):
            patch(new, 0x3293)

    def test_every_preimage_byte_in_every_bank_is_checked(self):
        for bank in range(1,9):
            for i in range(len(BODY)):
                old = self.fixture()
                old[bank*65536+0x3293+i] ^= 1
                with self.assertRaises(ValueError):
                    patch(old, 0x3293)
        with self.assertRaises(ValueError):
            patch(self.fixture()[:-1], 0x3293)
