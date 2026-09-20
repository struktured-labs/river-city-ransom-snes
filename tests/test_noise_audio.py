import unittest

import numpy as np

from tools.check_noise_audio import measure_noise, state, stimulus, nearest_clock_engine, NES_PERIODS, DSP_DIVISORS


class NoiseAudioTests(unittest.TestCase):
    def test_only_noise_table_changes_and_clock_error_never_increases(self):
        old = bytes([63]*6 + [62]*4 + [60, 59, 57, 56, 53, 50])
        engine = bytes(0x849) + old + bytes(32)
        corrected = nearest_clock_engine(engine)
        self.assertEqual(corrected[:0x849], engine[:0x849])
        self.assertEqual(corrected[0x859:], engine[0x859:])
        self.assertEqual(len(corrected), len(engine))
        for i, period in enumerate(NES_PERIODS):
            target = 1789773/period
            self.assertLessEqual(abs(32000/DSP_DIVISORS[corrected[0x849+i]&31]-target),
                                 abs(32000/DSP_DIVISORS[old[i]&31]-target))
            self.assertEqual(corrected[0x849+i]&0xE0, 32)
        with self.assertRaises(ValueError):
            nearest_clock_engine(corrected)
        with self.assertRaises(ValueError):
            nearest_clock_engine(engine+old)

    def test_schedule_boundaries_and_writes(self):
        self.assertEqual(state(59), (0, 0, 8, 63))
        self.assertEqual(state(60), (1, 1, 8, 63))
        self.assertEqual(state(960), (16, 15, 0, 63))
        self.assertEqual(state(1020), (17, 6, 8, 63))
        self.assertEqual(state(1080), (18, 6, 8, 49))
        self.assertEqual(state(1140), (19, 6, 8, 48))
        payload, grouped = stimulus()
        self.assertEqual(len(grouped), 1200)
        self.assertEqual(grouped[0], [(21, 8), (12, 63), (14, 0), (15, 0)])
        self.assertEqual(grouped[959], [(21, 0), (12, 63), (14, 15)])
        self.assertEqual(grouped[1019][-1], (15, 0))
        self.assertEqual(sum(len(w) for w in grouped), 62)
        self.assertTrue(payload)

    def test_noise_mute_and_failed_channels(self):
        rng = np.random.default_rng(701)
        pcm = rng.normal(0, 1000, (48000, 2))
        self.assertTrue(measure_noise(pcm, 48000, True)['passed'])
        self.assertTrue(measure_noise(pcm*0, 48000, False)['passed'])
        self.assertFalse(measure_noise(pcm, 48000, False)['passed'])
        self.assertFalse(measure_noise(pcm*0, 48000, True)['passed'])
        right = pcm.copy(); right[:, 1] = 0
        dropped = pcm.copy(); dropped[20000:24800] = 0
        clipped = pcm.copy(); clipped[100:200] = 32767
        for bad in (right, dropped, clipped, pcm*0+1000):
            self.assertFalse(measure_noise(bad, 48000, True)['passed'])

    def test_missing_or_nonfinite_audio_rejected(self):
        for bad in (np.zeros((10, 2)), np.zeros((48000, 1)), np.full((48000, 2), np.nan)):
            with self.assertRaises(ValueError):
                measure_noise(bad, 48000, True)


if __name__ == '__main__':
    unittest.main()
