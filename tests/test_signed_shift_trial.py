import unittest

from tools.build_signed_shift_trial import ADDRESS, ORIGINAL, OPTIMIZED, patch


class SignedShiftPatchTests(unittest.TestCase):
    def fixture(self):
        image=bytearray(2097152)
        for bank in range(1,9):
            at=bank*65536+ADDRESS
            image[at:at+len(ORIGINAL)]=ORIGINAL
        return image

    def test_only_eight_loops_and_checksum_change(self):
        image=self.fixture();result=patch(image)
        allowed=set(range(0xffdc,0xffe0))
        for bank in range(1,9):
            at=bank*65536+ADDRESS
            self.assertEqual(result[at:at+len(OPTIMIZED)],OPTIMIZED)
            allowed.update(range(at,at+len(ORIGINAL)))
        self.assertEqual(len(result),len(image))
        self.assertTrue(all(i in allowed for i,(a,b) in enumerate(zip(image,result)) if a!=b))
        self.assertEqual(int.from_bytes(result[0xffde:0xffe0],'little'),sum(result)&65535)

    def test_every_bank_preimage_required(self):
        for bank in range(1,9):
            image=self.fixture();image[bank*65536+ADDRESS+8]^=1
            with self.assertRaises(ValueError):patch(image)
