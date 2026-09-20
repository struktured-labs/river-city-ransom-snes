import unittest
import numpy as np

from tools.audit_capture_branch_step import window


class CaptureBranchStepTests(unittest.TestCase):
    def test_known_positive_and_negative_lag(self):
        signal=np.random.default_rng(23).normal(size=4000)
        for shift in (-32,0,32):
            raw=np.roll(signal,shift)
            r=window(raw,signal,0,1000,2000,64)
            self.assertEqual(r['diagnostic_offset_delta'],shift)
            self.assertGreater(r['diagnostic_correlation'],.999999)
            self.assertFalse(r['search_edge'])
            if shift:self.assertLess(r['fixed_correlation'],.2)

    def test_edge_is_reported_not_silently_passed(self):
        signal=np.random.default_rng(17).normal(size=4000)
        r=window(np.roll(signal,64),signal,0,1000,2000,64)
        self.assertTrue(r['search_edge'])

    def test_silent_and_incomplete_windows_rejected(self):
        signal=np.random.default_rng(19).normal(size=4000)
        for first,last in ((0,1000),(3500,4000)):
            with self.assertRaises(ValueError):window(signal,signal,0,first,last)
        with self.assertRaises(ValueError):window(np.zeros(4000),signal,0,1000,2000)


if __name__=='__main__':unittest.main()
