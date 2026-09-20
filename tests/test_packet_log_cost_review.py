import unittest

from tools.build_packet_log_cost_review import cost_summary


class PacketLogCostReviewTests(unittest.TestCase):
    def test_weighted_median_and_empty_rejection(self):
        self.assertEqual(cost_summary({'100': 1, '200': 3, '500': 1}),
                         dict(samples=5, minimum=100, maximum=500, median=200))
        with self.assertRaises(ValueError):
            cost_summary({})
