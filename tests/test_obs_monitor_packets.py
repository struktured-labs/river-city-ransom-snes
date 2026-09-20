import unittest

from tools.audit_obs_monitor_packets import analyze


TRACE = '''B,1
I,2,8,10,800,1000,48000
M,3,8,10,800,1000,20,0
L,4,8,0
Q,5,8,800
E,6,8
Z,7
'''


class MonitorPacketsTests(unittest.TestCase):
    def test_identity(self):
        r = analyze(TRACE)
        self.assertEqual(r['exact_input_monitor_matches'], 1)
        self.assertEqual(r['resampled_frames'], 800)
        self.assertFalse(r['successful_queue_publication_observed'])
        self.assertFalse(r['physical_audio_fixed'])

    def test_busy_packet_is_retained(self):
        r = analyze(TRACE.replace('L,4,8,0', 'L,4,8,16').replace('Q,5,8,800\n', ''))
        self.assertEqual(r['lock_busy_skipped_frames'], 800)
        self.assertEqual(r['resampled_frames'], 0)

    def test_missing_lock_rejected(self):
        with self.assertRaises(ValueError):
            analyze(TRACE.replace('L,4,8,0\n', ''))

    def test_duplicate_resample_rejected(self):
        with self.assertRaises(ValueError):
            analyze(TRACE.replace('Q,5,8,800\n', 'Q,5,8,800\nQ,5,8,800\n'))

    def test_locked_without_resample_is_not_a_pass(self):
        r = analyze(TRACE.replace('Q,5,8,800\n', ''))
        self.assertEqual(len(r['locked_without_successful_resample']), 1)

    def test_resampling_change_retained(self):
        r = analyze(TRACE.replace('Q,5,8,800', 'Q,5,8,768'))
        self.assertEqual(len(r['resized_callbacks']), 1)
        self.assertEqual(r['resampled_frames'], 768)

    def test_censoring_is_explicit(self):
        r = analyze(TRACE.replace('E,6,8\n', ''))
        self.assertEqual(len(r['censored_callbacks']), 1)
        self.assertEqual(r['completed_callbacks'], 0)
        self.assertEqual(len(r['unmatched_input_keys']), 1)

    def test_missing_end_rejected(self):
        with self.assertRaises(ValueError):
            analyze(TRACE.replace('Z,7\n', ''))

    def test_unmatched_monitor_retained(self):
        r = analyze(TRACE.replace('M,3,8,10,800,1000', 'M,3,8,10,800,1100'))
        self.assertEqual(r['exact_input_monitor_matches'], 0)
        self.assertEqual(len(r['unmatched_monitor_keys']), 1)

    def test_backward_same_thread_clock_rejected(self):
        with self.assertRaises(ValueError):
            analyze(TRACE.replace('E,6,8', 'E,4,8'))


if __name__ == '__main__':
    unittest.main()
