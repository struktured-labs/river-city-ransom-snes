import unittest

from tools.audit_interleaved_packet_log import sender_cost


class SenderCostTests(unittest.TestCase):
    def test_censored_boundaries_are_retained(self):
        rows = [['1','10','0','1','c0e306'], ['2','10','0','0','c0e080'],
                ['2','11','0','1','c0e306'], ['3','10','0','0','c0e080']]
        result = sender_cost(rows)
        self.assertEqual(len(result['censored']), 2)
        self.assertEqual(result['summary']['median'], 1364)

    def test_cross_frame_excluded_and_interior_mismatch_rejected(self):
        rows = [['1','250','0','0','c0e080'], ['2','10','0','1','c0e306'],
                ['2','10','0','0','c0e080'], ['2','11','0','1','c0e306']]
        self.assertEqual(len(sender_cost(rows)['excluded']), 1)
        rows[2][3] = '1'
        with self.assertRaises(ValueError):
            sender_cost(rows)
