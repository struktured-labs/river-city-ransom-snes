import unittest
from tools.audit_current_audio_pipeline import spc_pairs,decompose_spc


class Pairs(unittest.TestCase):
    def rows(self):return [['P','1','10','0','0'],['R','1','20','0','0'],['P','2','30','0','0'],['R','2','50','0','0']]

    def test_exact_decomposition(self):
        a,b=spc_pairs(self.rows())
        self.assertEqual(decompose_spc(a,b),dict(receive_gap_ticks=20,processing_change_ticks=10,ready_gap_ticks=30))
        broken=dict(b);broken['processing']+=1
        with self.assertRaises(ValueError):decompose_spc(a,broken)

    def test_missing_duplicate_and_censored(self):
        for i in range(4):
            bad=self.rows();bad.pop(i)
            with self.assertRaises(ValueError):spc_pairs(bad)
        for i in range(4):
            bad=self.rows();bad.insert(i,bad[i])
            with self.assertRaises(ValueError):spc_pairs(bad)
