import unittest

from tools.build_main_phase_trial import patch, SIZE, PHASE
from tools.build_inline_pitch_trial import checksum
from tools.check_main_phase_reprobe import validate_images


class MainPhaseReprobeTests(unittest.TestCase):
    def fixture(self):
        image = bytearray(b'\xff'*0x200000)
        helper = bytearray(b'\xea'*SIZE)
        helper[:3] = bytes.fromhex('084820')
        helper[-3:] = bytes.fromhex('606860')
        helper[70:73] = bytes.fromhex('c98090')
        for bank in range(1, 9):
            at = bank*65536+0x3456
            image[at:at+SIZE] = helper
        return image, helper

    def test_only_eight_immediates_and_checksum(self):
        old, body = self.fixture()
        new, sites = patch(old, 0x3456)
        self.assertEqual(len(set(sites)), 8)
        self.assertTrue(all(old[i] == 128 and new[i] == PHASE for i in sites))
        allowed = set(sites) | set(range(0xffdc, 0xffe0))
        self.assertTrue(all(i in allowed for i,(a,b) in enumerate(zip(old,new)) if a != b))
        body[71] = PHASE
        self.assertEqual(validate_images(old, new, 0x3456, body), sites)
        with self.assertRaises(ValueError):
            patch(new, 0x3456)

    def test_missing_ambiguous_or_short_preimage_rejected(self):
        for mode in ('short', 'missing', 'ambiguous', 'start', 'end'):
            old, _ = self.fixture()
            if mode == 'short':
                old = old[:-1]
            elif mode == 'missing':
                old[0x83456+71] = 127
            elif mode == 'ambiguous':
                old[0x83456+40:0x83456+43] = bytes.fromhex('c98090')
            elif mode == 'start':
                old[0x83456] = 0
            else:
                old[0x83456+SIZE-1] = 0
            with self.assertRaises(ValueError, msg=mode):
                patch(old, 0x3456)

    def test_valid_checksum_cannot_hide_unrelated_edits(self):
        old, body = self.fixture()
        new, _ = patch(old, 0x3456)
        body[71] = PHASE
        for at in (0x8000, 0x83456+10, 0x1fffff):
            altered = bytearray(new)
            altered[at] ^= 1
            checksum(altered)
            with self.assertRaises(ValueError):
                validate_images(old, altered, 0x3456, body)

    def test_oracle_must_match_all_mirrored_bodies(self):
        old, body = self.fixture()
        old[0x83456+10] ^= 1
        new, _ = patch(old, 0x3456)
        body[71] = PHASE
        with self.assertRaises(ValueError):
            validate_images(old, new, 0x3456, body)
