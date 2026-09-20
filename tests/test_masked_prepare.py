import unittest

from tools.audit_masked_prepare import missed_vblank


class MaskedPrepareTests(unittest.TestCase):
    def test_complete_masked_vblank_and_observed_gap(self):
        a=dict(frame=10,line=231,clock=100);b=dict(frame=11,line=10,clock=200)
        prev=dict(frame=9,clock=0);nxt=dict(frame=11,clock=300)
        self.assertTrue(missed_vblank(a,b,prev,nxt))
        self.assertFalse(missed_vblank(a,dict(b,frame=10,line=255),prev,nxt))
        self.assertFalse(missed_vblank(a,b,dict(prev,frame=10),nxt))
        self.assertFalse(missed_vblank(a,b,prev,dict(nxt,clock=150)))
