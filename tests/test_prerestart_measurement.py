import unittest

from tools.check_game_prerestart import characterize
from tools.review_game_prerestart import latch_index


class MeasurementTests(unittest.TestCase):
    def test_bootstrap_latches_remain_distinct(self):
        events = [dict(packet=0, voice=0, keyon_write=dict(tick=t)) for t in (100, 200)]
        self.assertEqual(len(latch_index(events)), 2)
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            latch_index(events+events[:1])

    def test_partial_pitch_is_detected_before_kon(self):
        # Voice0 reads low at tick950, high at951 for source tick959/V4 tick960.
        # New low=2 is visible, old high=1 is still live: actual pitch=258.
        writes = [dict(register=r, value=v, tick=t) for r, v, t in
                  [(2, 1, 100), (3, 1, 110), (2, 2, 945), (3, 2, 955)]]
        event = dict(voice=0, packet=1, configuration=[dict(tick=940)], keyon=dict(tick=1000))
        source = dict(tick=959, previous_delay=0, pitch=258)
        groups = {30: dict(sources={0: source}, amplitudes={(0, 0): 12, (0, 1): 13})}
        result = characterize(event, 1020, groups, writes)
        self.assertEqual((result['split_pitch_samples'], result['nonzero_split_samples']), (1, 1))
        source['pitch'] = 514
        with self.assertRaisesRegex(ValueError, 'Unexplained actual'):
            characterize(event, 1020, groups, writes)


if __name__ == '__main__':
    unittest.main()
