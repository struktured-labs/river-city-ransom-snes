import unittest
from tools.review_receiver_ablation import identical_payloads

class PayloadComparisonTest(unittest.TestCase):
    def test_timing_retained_separately(self):
        self.assertTrue(identical_payloads([{'bytes':'01','frame':1}],[{'bytes':'01','frame':2}]))

    def test_missing_changed_reordered_and_empty(self):
        a=[{'bytes':'01'},{'bytes':'02'}]
        for b in (a[:-1],list(reversed(a)),[{'bytes':'03'},a[1]],[]):
            self.assertFalse(identical_payloads(a,b))
        self.assertFalse(identical_payloads([],[]))
