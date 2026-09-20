import unittest

from tools.build_main_phase_trial import SIZE
from tools.build_phase_balance_trial import patch,PHASE


class PhaseBalanceTests(unittest.TestCase):
    def fixture(self):
        image = bytearray(b'\xff'*0x200000)
        body = bytearray(b'\xea'*SIZE)
        body[:3] = bytes.fromhex('084820')
        body[-3:] = bytes.fromhex('606860')
        body[70:73] = bytes.fromhex('c94090')
        for bank in range(1,9):
            image[bank*65536+0x3456:bank*65536+0x3456+SIZE] = body
        return image

    def test_eight_immediates_only_and_repetition_rejected(self):
        old = self.fixture()
        new,sites = patch(old,0x3456)
        self.assertEqual(len(set(sites)),8)
        self.assertTrue(all(old[i]==64 and new[i]==PHASE for i in sites))
        allowed = set(sites)|set(range(0xffdc,0xffe0))
        self.assertTrue(all(i in allowed for i,(a,b) in enumerate(zip(old,new)) if a!=b))
        self.assertEqual(sum(new)&65535,int.from_bytes(new[0xffde:0xffe0],'little'))
        with self.assertRaises(ValueError):
            patch(new,0x3456)

    def test_all_mirrored_bytes_are_bound(self):
        for bank in range(1,9):
            for i in range(SIZE):
                image = self.fixture()
                image[bank*65536+0x3456+i] ^= 1
                with self.assertRaises(ValueError):
                    patch(image,0x3456)
        with self.assertRaises(ValueError):
            patch(self.fixture()[:-1],0x3456)
