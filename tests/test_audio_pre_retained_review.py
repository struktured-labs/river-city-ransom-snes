import unittest
from tools.review_audio_pre_retained import timing_improves


class Timing(unittest.TestCase):
    def test_both_tails_required(self):
        base=dict(minimum_ms=12,maximum_ms=21)
        self.assertFalse(timing_improves(base,dict(minimum_ms=10,maximum_ms=20)))
        self.assertFalse(timing_improves(base,dict(minimum_ms=13,maximum_ms=23)))
        self.assertFalse(timing_improves(base,base))
        self.assertTrue(timing_improves(base,dict(minimum_ms=12,maximum_ms=20)))
