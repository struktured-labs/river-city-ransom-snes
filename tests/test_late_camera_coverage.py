import unittest
from tools.review_late_camera_coverage import coverage
from tests.test_camera_export_episode import row


class LateCameraCoverageTests(unittest.TestCase):
    def test_stationary_and_sparse_samples_do_not_count_as_moving_coverage(self):
        rows=[row(0,10),row(1,12),row(2,14,2),row(3,24,12)]
        result=coverage(rows)
        self.assertEqual(result['two_tick_pairs'],2)
        self.assertEqual(result['moving_two_tick_pairs'],1)
        self.assertEqual(result['gaps'],1)
        rows[2]['room']=1
        self.assertEqual(coverage(rows)['moving_two_tick_pairs'],0)
