import unittest

from tools.build_saturating_shift_trial import patch, ADDRESS, HELPER, HOOK, OPTIMIZED


class SaturatingShiftPatchTests(unittest.TestCase):
    def fixture(self):
        image = bytearray(b'\xff'*2097152)
        for bank in range(1,9):
            at = bank*65536+ADDRESS
            image[at:at+20] = OPTIMIZED+bytes.fromhex('a52638')
        return image

    def test_exact_scope_and_repeat_refused(self):
        image = self.fixture()
        helper = b'\xea'*64
        result = patch(image,helper)
        allowed = set(range(0xffdc,0xffe0))
        for bank in range(1,9):
            base = bank*65536
            self.assertEqual(result[base+ADDRESS:base+ADDRESS+17],HOOK)
            self.assertEqual(result[base+HELPER:base+HELPER+64],helper)
            allowed.update(range(base+ADDRESS,base+ADDRESS+17))
            allowed.update(range(base+HELPER,base+HELPER+64))
        self.assertTrue(all(i in allowed for i,(a,b) in enumerate(zip(image,result)) if a != b))
        with self.assertRaises(ValueError):
            patch(result,helper)

    def test_occupied_helper_refused(self):
        image = self.fixture()
        image[5*65536+HELPER] = 0
        with self.assertRaises(ValueError):
            patch(image,b'\xea'*64)

    def test_changed_continuation_refused(self):
        image = self.fixture()
        image[8*65536+ADDRESS+17] = 0
        with self.assertRaises(ValueError):
            patch(image,b'\xea'*64)

    def test_wrong_helper_size_refused(self):
        with self.assertRaises(ValueError):
            patch(self.fixture(),b'\xea'*63)
