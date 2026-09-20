import unittest

from tools.review_startup_pitch_trial import startup_window, compare_timeline


class WindowTests(unittest.TestCase):
    def test_callback_difference_is_retained_not_a_pass(self):
        a = [dict(source_frame=1, host_frame=35, start_sample=10, end_sample=20)]
        b = [dict(a[0], start_sample=9)]
        result = compare_timeline(a, b, 20, 21)
        self.assertFalse(result['exact_callback_timeline_equal'])
        self.assertFalse(result['sample_count_equal'])
        self.assertEqual(len(result['callback_differences']), 1)
        with self.assertRaisesRegex(ValueError, 'cadence'):
            compare_timeline(a, [dict(b[0], host_frame=36)], 20, 21)

    def test_bounds_use_actual_latch_and_voice_read_phase(self):
        event = dict(voice=0, packet=1, tick=1030, keyon_write=dict(tick=1000),
                     samples=[dict(tick=1031+32*i) for i in range(96)], first_pitch_matches=True)
        ready = {1: dict(tick=1400)}
        def run(low, high):
            writes = [dict(packet=1, register=2, tick=low), dict(packet=1, register=3, tick=high)]
            return startup_window(event, writes, ready)['passed']
        self.assertTrue(run(1100, 1112))
        self.assertFalse(run(1062, 1074))
        self.assertFalse(run(1213, 1225))
        with self.assertRaisesRegex(ValueError, 'complete pitch pair'):
            startup_window(event, [], ready)


if __name__ == '__main__':
    unittest.main()
