import unittest

import numpy as np

from tools.review_phase80_completion import measure, sensitivity


class NativeAudioTests(unittest.TestCase):
    def test_native_rate_is_not_treated_as_48k(self):
        pcm = np.full((64080,2),100,dtype=np.int16)
        pcm[32040:32361] = 0
        result = measure(pcm,32040)
        self.assertEqual(result['seconds'],2)
        self.assertEqual(result['longest_exact_zero_frames'],321)
        self.assertEqual(result['exact_zero_runs_at_least_10ms'],[
            dict(first_sample=32040,last_sample=32361,seconds=321/32040)])

    def test_full_signed_range_and_channel_selection(self):
        pcm = np.ones((32040,2),dtype=np.int16)
        pcm[100,1],pcm[101,1] = -32768,32767
        result = measure(pcm,32040,1)
        self.assertEqual(result['max_adjacent_step'],65535)
        self.assertEqual(result['clipped_samples'],2)
        self.assertEqual(result['strongest_separated_events'][0]['sample'],101)
        self.assertEqual(result['strongest_separated_events'][0]['channel'],1)

    def test_real_mutations_detected_at_native_rate(self):
        pcm = np.full((64080,2),400,dtype=np.int16)
        self.assertTrue(all(sensitivity(pcm,32040).values()))

    def test_bad_format_rejected(self):
        for pcm,rate in ((np.ones((32040,2)),32040), (np.ones((32040,1),dtype=np.int16),32040),
                         (np.ones((32040,2),dtype=np.int16),0)):
            with self.assertRaises(ValueError):
                measure(pcm,rate)
