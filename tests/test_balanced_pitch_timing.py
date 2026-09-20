import unittest
from tools.audit_balanced_pitch_timing import compare


class BalancedPitchTimingTests(unittest.TestCase):
    def writes(self):
        return [dict(register=2,value=34,packet=1,tick=100),
            dict(register=3,value=2,packet=1,tick=117),
            dict(register=0,value=100,packet=1,tick=124)]

    def test_only_low_moves_nine_clocks(self):
        a=self.writes();b=self.writes();b[0]['tick']+=9
        self.assertEqual(compare(a,b)['expected_shifts'],{9:1,0:2})
        for index,key in ((0,'tick'),(1,'tick'),(2,'tick'),(0,'value'),(0,'packet')):
            bad=[dict(r) for r in b];bad[index][key]+=1
            with self.assertRaises(ValueError):compare(a,bad)

    def test_missing_writes_and_unsupported_gap_rejected(self):
        a=self.writes()
        with self.assertRaises(ValueError):compare(a,a[:-1])
        a[1]['tick']+=1
        with self.assertRaises(ValueError):compare(a,a)
