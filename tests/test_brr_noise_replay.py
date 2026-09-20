import unittest

from tools.build_brr_noise_replay import noise_sample,patch


class BrrNoiseReplayTests(unittest.TestCase):
    def test_full_cycle_and_exact_single_sample_padding(self):
        data=noise_sample();self.assertEqual(len(data),18432)
        values=[]
        for at in range(0,len(data),9):
            self.assertEqual(data[at],0xc3 if at+9==len(data) else 0xc0)
            values.extend(n-16 if n>=8 else n for b in data[at+1:at+9] for n in (b>>4,b&15))
        state=1;seen=set()
        for level in values[:-1]:
            self.assertNotIn(state,seen);seen.add(state)
            self.assertEqual(level,-4 if state&1 else 4)
            state=(state>>1)|(((state^(state>>1))&1)<<14)
        self.assertEqual((len(seen),state),(32767,1))
        self.assertEqual(values[-1],values[-2])

    def test_unknown_engine_fails_closed(self):
        for data in (b'',bytes(12415)):
            with self.assertRaises(ValueError):patch(data)
