import unittest
from tools.audit_receiver_text_deadlines import attribute


def records(source,prepared,vram):
    return [dict(frame=f,source=int(f>=source),prepared=int(f>=prepared),vram=int(f>=vram))
            for f in range(8)]


class ReceiverAttributionTests(unittest.TestCase):
    def test_source_phase_not_consumer_regression(self):
        result=attribute(records(1,2,4),records(3,4,5),1)
        self.assertEqual((result['source_phase'],result['prepare_lag_change'],
                          result['publish_lag_change'],result['display_delay']),(2,0,-1,1))
        self.assertFalse(result['equal_source_timeline'])

    def test_ready_row_delayed(self):
        result=attribute(records(1,2,3),records(1,2,4),1)
        self.assertEqual((result['source_phase'],result['prepare_lag_change'],
                          result['publish_lag_change'],result['display_delay']),(0,0,1,1))
        self.assertTrue(result['equal_source_timeline'])

    def test_censoring_and_order_rejected(self):
        for arm in (records(0,1,2),records(1,2,9),records(3,2,4),[]):
            with self.assertRaises(ValueError):attribute(records(1,2,3),arm,1)

    def test_changed_generation_rejected(self):
        arm=records(1,2,3);arm[-1]['vram']=0
        with self.assertRaises(ValueError):attribute(records(1,2,3),arm,1)
