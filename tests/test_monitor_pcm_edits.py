import unittest
import numpy as np
from tools.audit_monitor_pcm_edits import walk


class MonitorEditsTests(unittest.TestCase):
    def test_exact_deleted_block(self):
        x = np.random.default_rng(88).integers(-1000, 1000, (5000, 2), dtype=np.int32)
        y = np.concatenate([x[:2000], x[2032:]])
        r = walk(x, y, 500, 4500, 0)
        self.assertTrue(r['complete'])
        self.assertEqual(r['net_reference_advance'], 32)

    def test_no_mutation_pass(self):
        x = np.zeros((5000, 2), dtype=np.int32)
        r = walk(x, x.copy(), 500, 4000, 0)
        self.assertTrue(r['complete'])
        self.assertEqual(r['edits'], [])

    def test_corruption_not_mislabeled_drop(self):
        x = np.random.default_rng(89).integers(-1000,1000,(5000,2),dtype=np.int32)
        y = x.copy(); y[1000,0] += 1
        r = walk(x, y, 500, 4000, 0)
        self.assertFalse(r['complete'])
        self.assertEqual(r['reason'], 'No unique bounded edit')

    def test_repeated_context_ambiguity_retained(self):
        x = np.zeros((5000,2),dtype=np.int32); y=x.copy(); y[1000]=1
        r = walk(x,y,500,4000,0)
        self.assertFalse(r['complete'])
        self.assertGreater(len(r['edits'][0]['candidates']),1)


if __name__ == '__main__':
    unittest.main()
