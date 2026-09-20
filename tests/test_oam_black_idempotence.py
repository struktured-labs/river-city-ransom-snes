import unittest
from tools.audit_oam_blank_idempotent import spans
from tests.test_oam_blank_route import event


class BlackIdempotenceTests(unittest.TestCase):
    def test_real_pattern_retains_repeated_black_writes(self):
        es=[event('R',0,18),event('B',19,19,1),event('B',20,238,2),event('B',19,19,3),event('B',19,19,4)]
        r=spans(es,1);self.assertTrue(r['passed']);self.assertEqual(len(r['repeated_black_writes']),2)

    def test_rendered_duplicate_and_mixed_overlap_fail(self):
        for a,b in (('R','R'),('R','B'),('B','R')):
            self.assertFalse(spans([event(a,0,238),event(b,19,19,1)],1)['passed'])

    def test_missing_black_cannot_be_replaced_by_redundancy(self):
        self.assertFalse(spans([event('R',0,18),event('B',19,19,1),event('B',19,19,2)],1)['passed'])

    def test_wrong_black_state_rejected(self):
        self.assertFalse(spans([dict(event('B',0,238),blank=0)],1)['passed'])
