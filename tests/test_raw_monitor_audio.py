import unittest
import numpy as np

from tools.audit_raw_monitor_audio import locate,score,compare_gaps


class RawMonitorAudioTests(unittest.TestCase):
    def fixture(self):
        data=np.random.default_rng(25).normal(size=2000)
        return np.r_[np.zeros(310),data,np.zeros(200)],data

    def test_exact_delayed_copy_has_one_frozen_offset(self):
        raw,aac=self.fixture();result=locate(raw,aac,200,800)
        self.assertEqual(result['offset_samples'],310)
        self.assertAlmostEqual(result['training_correlation'],1)
        self.assertAlmostEqual(score(raw,aac,310,900,1100),1)

    def test_heldout_change_is_not_refitted_away(self):
        raw,aac=self.fixture();offset=locate(raw,aac,200,800)['offset_samples']
        raw[1210:1410]=0
        self.assertIsNone(score(raw,aac,offset,900,1100))

    def test_silent_nonfinite_or_missing_alignment_rejected(self):
        raw,aac=self.fixture()
        for bad in (np.zeros_like(raw),np.full_like(raw,np.nan),np.zeros(10)):
            with self.assertRaises(ValueError):locate(bad,aac,200,800)

    def test_common_gap_and_aac_only_gap_distinguished(self):
        raw=np.ones((1000,2));aac=raw.copy();raw[200:300]=0;aac[200:300]=0;aac[600:700]=0
        gaps=compare_gaps(raw,aac,1000,0)
        self.assertEqual([g['raw_exact_zero_fraction'] for g in gaps],[1,0])

    def test_uncovered_tail_not_counted_as_common_silence(self):
        raw=np.ones((1000,2));aac=np.ones((1000,2));aac[800:]=0
        gap=compare_gaps(raw,aac,1000,100)[0]
        self.assertFalse(gap['fully_covered_in_raw']);self.assertIsNone(gap['raw_exact_zero_fraction'])
