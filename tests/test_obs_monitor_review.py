import unittest

from tools.build_obs_monitor_review import coverage


class MonitorReviewTests(unittest.TestCase):
    def test_bracketed_interval(self):
        trace = dict(callbacks=[dict(clock=1_000_000_000, duration_ns=10),
                                dict(clock=5_000_000_000, duration_ns=10)], censored_callbacks=[])
        episode = dict(ready_received_monotonic=2, input_finished_monotonic=4)
        self.assertTrue(coverage(trace, episode)['input_interval_bracketed'])
        self.assertFalse(coverage(trace, episode)['per_sample_timestamp_join'])

    def test_short_trace_rejected(self):
        trace = dict(callbacks=[dict(clock=1_000_000_000, duration_ns=10)], censored_callbacks=[])
        with self.assertRaises(ValueError):
            coverage(trace, dict(ready_received_monotonic=2, input_finished_monotonic=4))

    def test_censored_trace_rejected(self):
        with self.assertRaises(ValueError):
            coverage(dict(callbacks=[], censored_callbacks=[{}]), {})


if __name__ == '__main__':
    unittest.main()
