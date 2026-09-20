import unittest
from tools.audit_sound_service_phases import pair, MS_PER_CLOCK


def event(kind, clock, stack=470):
    return [str(x) for x in (kind, 1, 80, 0, clock, 'c1fa54', 'ad', 0, 0, 0,
                             stack, 0, 0, 1, 192, 0, 0, 0)]


class SoundServicePhases(unittest.TestCase):
    def test_decomposition(self):
        calls, gaps = pair([event(0, 100), event(1, 120), event(0, 200), event(1, 250)])
        self.assertEqual(len(calls), 2)
        self.assertAlmostEqual(gaps[0]['entry_gap_ms'], 100 * MS_PER_CLOCK)
        self.assertAlmostEqual(gaps[0]['duration_change_ms'], 30 * MS_PER_CLOCK)
        self.assertAlmostEqual(gaps[0]['return_gap_ms'], 130 * MS_PER_CLOCK)

    def test_reject_broken_envelopes(self):
        for events in ([event(1, 100)], [event(0, 100), event(0, 120)],
                       [event(0, 100), event(1, 120, 469)], [event(0, 100)],
                       [event(0, 100), event(1, 90)]):
            with self.subTest(events=events), self.assertRaises(ValueError):
                pair(events)
