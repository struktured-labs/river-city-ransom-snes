import unittest

from tools.audit_retrigger_transient import evaluate


class RetriggerTransientAuditTests(unittest.TestCase):
    def reference(self):
        return dict(max_step_to_signal_peak=1.0, max_step_to_full_scale=.17,
                    longest_near_zero_ms=.03, clipped_fraction=0)

    def candidate(self):
        return dict(max_step_to_signal_peak=.98, max_step_to_full_scale=.08,
                    longest_near_zero_ms=.04, clipped_fraction=0)

    def test_bounded_candidate_passes(self):
        gates, limits = evaluate(self.reference(), self.candidate())
        self.assertTrue(all(gate['passed'] for gate in gates))
        self.assertEqual(limits['longest_near_zero_ms'], .5)

    def test_spike_dropout_and_clipping_fail_closed(self):
        for field, value in (('max_step_to_signal_peak', 1.5),
                             ('max_step_to_full_scale', .5),
                             ('longest_near_zero_ms', 1.0),
                             ('clipped_fraction', .001)):
            candidate = self.candidate()
            candidate[field] = value
            gates, _ = evaluate(self.reference(), candidate)
            self.assertFalse(all(gate['passed'] for gate in gates), field)
