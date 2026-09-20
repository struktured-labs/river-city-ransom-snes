import unittest
from tools.build_alias_audio48 import patch, PATTERNS


class AliasAudio48Tests(unittest.TestCase):
    def setUp(self):
        self.image = bytearray(b'\xff'*(9*65536))
        for bank in range(1,9):
            for offset, code in PATTERNS:
                at = bank*65536+offset
                self.image[at:at+len(code)] = code

    def test_exact_limited_changes_and_matching_timer_recovery(self):
        after, sites = patch(self.image)
        diff = {i for i,(a,b) in enumerate(zip(self.image,after)) if a != b}
        self.assertEqual(len(sites),16)
        self.assertTrue(set(sites) <= diff <= set(sites)|set(range(0xffdc,0xffe0)))
        for at in sites: self.assertEqual(after[at],48)
        self.assertEqual(sum(after)&65535,int.from_bytes(after[0xffde:0xffe0],'little'))
        # Actual emitted CPX immediate and BCC operand: preserve the recovery
        # branch, admitting the previously late line48 through line79 range.
        for bank in range(1,9):
            at=bank*65536+0x78cf
            self.assertEqual(after[at:at+4],bytes.fromhex('e0309007'))
            for line in range(256):
                self.assertEqual(line >= after[at+1], line >= 48)
        with self.assertRaises(ValueError): patch(after)

    def test_every_guard_byte_mutation_rejected(self):
        for bank in range(1,9):
            for offset, code in PATTERNS:
                for index in range(len(code)):
                    damaged=self.image.copy()
                    damaged[bank*65536+offset+index]^=1
                    with self.assertRaises(ValueError): patch(damaged)
