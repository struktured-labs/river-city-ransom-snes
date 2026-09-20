import struct
import unittest
from tools.audit_raster_service import counters


class RasterServiceTests(unittest.TestCase):
    def sample(self, scheduled, missed, served, late, pending=0):
        memory = bytearray(131072)
        struct.pack_into('<4H', memory, 0x1CA8, scheduled, missed, served, late)
        memory[0x1CA3] = pending
        return counters(memory)

    def test_completed_or_one_pending(self):
        self.assertTrue(self.sample(100, 0, 100, 0)['passed'])
        self.assertTrue(self.sample(100, 0, 99, 0, 1)['passed'])

    def test_missed_balances_but_fails(self):
        row = self.sample(1140, 56, 1084, 61)
        self.assertTrue(row['balanced'])
        self.assertFalse(row['passed'])

    def test_deadline_and_missing_work_fail(self):
        self.assertFalse(self.sample(100, 0, 100, 1)['passed'])
        self.assertFalse(self.sample(100, 0, 99, 0)['passed'])
        self.assertFalse(self.sample(0, 0, 0, 0)['passed'])

    def test_recovered_work_is_not_on_time(self):
        memory = bytearray(131072)
        struct.pack_into('<4H', memory, 0x1CA8, 100, 0, 100, 0)
        struct.pack_into('<H', memory, 0x1CB8, 1)
        result = counters(memory)
        self.assertTrue(result['balanced'])
        self.assertFalse(result['passed'])
