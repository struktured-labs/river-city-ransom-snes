import unittest

from tools.build_ordinary_early_audio import patch
from tools.review_ordinary_audio_trial import compare_commands


class OrdinaryAudioTrialTests(unittest.TestCase):
    def test_packet_identity_payload_and_coverage_guard(self):
        a=[dict(nmi=1,bytes='0102'),dict(nmi=2,bytes='0304')]
        self.assertEqual(compare_commands(a,a),2)
        for b in (a[:1],[dict(nmi=3,bytes='0102'),a[1]],
                  [a[0],dict(nmi=2,bytes='0305')]):
            with self.assertRaises(ValueError):compare_commands(a,b)

    def test_patch_is_bounded_and_rejects_occupied_slot(self):
        image=bytearray(b'\xff'*0x200000);image[0x818f:0x8193]=bytes.fromhex('68dc001c')
        helper=bytes.fromhex('68dc001c')+b'\xff'*508
        result=patch(image,helper,0x818f)
        self.assertEqual(result[0x818f:0x8193],bytes.fromhex('5c0076c1'))
        for bank in range(1,9):self.assertEqual(result[bank*65536+0x7600:bank*65536+0x7800],helper)
        image[0x17600]=0
        with self.assertRaises(ValueError):patch(image,helper,0x818f)


if __name__=='__main__':unittest.main()
