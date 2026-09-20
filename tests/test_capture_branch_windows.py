import unittest
import numpy as np

from tools.audit_capture_branch_windows import scan


class CaptureBranchWindowsTests(unittest.TestCase):
    def test_piecewise_lag_and_fixed_failures_are_both_retained(self):
        reference = np.random.default_rng(18).normal(size=5000)
        raw = reference.copy()
        raw[2000:] = reference[1904:4904]
        rows = scan(raw, reference, 0, 1000, 1000, 4000, 1000, 128)
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[-1]['diagnostic_offset_delta'], 96)
        self.assertLess(rows[-1]['fixed_correlation'], .2)
        self.assertGreater(rows[-1]['diagnostic_correlation'], .999999)

    def test_silent_and_uncovered_windows_stay_in_report(self):
        reference = np.random.default_rng(20).normal(size=3000)
        rows = scan(np.zeros(3000), reference, 0, 1000, 0, 3000, 1000, 128)
        self.assertEqual(len(rows), 3)
        self.assertTrue(all(not r['searchable'] for r in rows))
        self.assertEqual([(r['first'], r['last']) for r in rows], [(0, 1000), (1000, 2000), (2000, 3000)])


if __name__ == '__main__':
    unittest.main()
