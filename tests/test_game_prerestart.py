import unittest

from tools.check_game_prerestart import select, characterize


def event(packet=1, voice=0, tick=1000, gap=100):
    return dict(packet=packet, voice=voice, keyon=dict(tick=tick), configuration=[
        dict(tick=tick-gap, register=16*voice+2, previous_value=10, value=11)])


class SelectionTests(unittest.TestCase):
    def test_selection_is_timing_only_and_bounded(self):
        rows = [event(i+1, v, 10000+i*10000+v*1000, i+20) for i in range(50) for v in (0, 1)]
        chosen, windows = select(rows)
        self.assertEqual(len(chosen), 24)
        self.assertLessEqual(len(windows), 64)
        self.assertEqual(select(list(reversed(rows))), (chosen, windows))

    def test_unchanged_configuration_is_not_eligible(self):
        row = event(); row['configuration'][0]['value'] = 10
        with self.assertRaisesRegex(ValueError, 'No changed'):
            select([row])

    def test_overlapping_windows_merged_without_losing_events(self):
        chosen, windows = select([event(), event(2, 1, 1010)])
        self.assertEqual(len(chosen), 2)
        self.assertEqual(len(windows), 1)
        self.assertTrue(all(windows[0][0] <= r['window'][0] < r['window'][1] <= windows[0][1]
                            for r in chosen))

    def test_wrong_latch_and_missing_samples_fail(self):
        with self.assertRaisesRegex(ValueError, 'Wrong hardware'):
            characterize(event(), 999, {}, [])
        with self.assertRaisesRegex(ValueError, 'No setup samples'):
            characterize(event(), 1020, {}, [])


if __name__ == '__main__':
    unittest.main()
