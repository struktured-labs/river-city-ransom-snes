import unittest
import numpy as np
from tools.audit_common_pcm_branches import compare


class CommonBranchTests(unittest.TestCase):
    def test_raw_only_deleted_samples_localized(self):
        common = np.random.default_rng(91).normal(size=30000)
        raw = np.r_[common[:16000], common[16032:]]
        r = compare(common, raw, common.copy(), 0, rate=1000)
        self.assertTrue(all(w['diagnostic_offset_delta'] == 0 for w in r['common_vs_aac_windows']))
        self.assertEqual(r['common_vs_raw_windows'][-1]['diagnostic_offset_delta'], 32)
        self.assertLess(r['common_vs_raw_windows'][-1]['fixed_correlation'], .2)

    def test_aac_only_deleted_samples_localized(self):
        common = np.random.default_rng(92).normal(size=30000)
        aac = np.r_[common[:16000], common[16032:]]
        r = compare(common, common.copy(), aac, 0, rate=1000)
        self.assertTrue(all(w['diagnostic_offset_delta'] == 0 for w in r['common_vs_raw_windows']))
        self.assertEqual(r['common_vs_aac_windows'][-1]['diagnostic_offset_delta'], 32)

    def test_silent_common_cannot_pass(self):
        with self.assertRaises(ValueError):
            compare(np.zeros(30000), np.zeros(30000), np.zeros(30000), 0, rate=1000)


if __name__ == '__main__':
    unittest.main()
