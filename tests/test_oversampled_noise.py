import unittest

from tools.build_oversampled_noise_replay import sample


class OversampledNoiseTests(unittest.TestCase):
    def test_full_period_pair_hold_and_declared_level_only_delta(self):
        a,b=sample(4),sample(7)
        self.assertEqual((len(a),len(b)),(36864,36864))
        for at in range(0,len(a),9):
            self.assertEqual(a[at],0xc3 if at+9==len(a) else 0xc0)
            self.assertEqual(a[at],b[at])
            for x,y in zip(a[at+1:at+9],b[at+1:at+9]):
                self.assertIn((x,y),((0x44,0x77),(0xcc,0x99)))
        self.assertEqual(a[-1],a[-2])
        decoded=[]
        for at in range(0,len(a),9):
            decoded.extend(-4 if byte==0xcc else 4 for byte in a[at+1:at+9])
        state=1;seen=set()
        for value in decoded[:-1]:
            self.assertNotIn(state,seen);seen.add(state)
            self.assertEqual(value,-4 if state&1 else 4)
            state=(state>>1)|(((state^(state>>1))&1)<<14)
        self.assertEqual((len(seen),state),(32767,1))
        self.assertEqual(decoded[-1],decoded[-2])
        for invalid in (0,3,8):
            with self.assertRaises(ValueError):sample(invalid)
