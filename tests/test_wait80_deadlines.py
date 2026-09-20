import unittest
from tools.audit_wait80_deadlines import classify


def records(source,prepared,display):
    return [dict(frame=f,source=int(f>=source),prepared=int(f>=prepared),vram=int(f>=display))
            for f in range(6)]


class AttributionTests(unittest.TestCase):
    def test_preparation_delay_not_consumer_delay(self):
        r=classify(records(1,2,3),records(1,3,4),1)
        self.assertEqual((r['prepare_delay'],r['display_delay']),(1,1))
        self.assertEqual((r['publication_lag_before'],r['publication_lag_after']),(1,1))

    def test_ready_row_consumer_delay_is_distinct(self):
        r=classify(records(1,2,3),records(1,2,4),1)
        self.assertEqual((r['prepare_delay'],r['display_delay']),(0,1))
        self.assertEqual(r['publication_lag_after'],2)

    def test_censoring_and_changed_source_fail_closed(self):
        for other in (records(0,1,2),records(1,2,6),records(2,3,4)):
            with self.assertRaises(ValueError):classify(records(1,2,3),other,1)
