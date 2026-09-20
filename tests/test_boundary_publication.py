import unittest
from tools.audit_boundary_publication import compare


class BoundaryPublication(unittest.TestCase):
    def fixture(self):
        a = bytearray(196608); b = bytearray(a)
        index = 2*32+3; offset = 0x24000+index*2
        a[0x12000+index] = b[0x12000+index] = 192
        a[offset] = 192
        return a, b, offset, index

    def test_regression_and_improvement_are_distinct(self):
        a, b, _, _ = self.fixture()
        self.assertEqual(compare(a, b)[0]['verdict'], 'parent_current')
        self.assertEqual(compare(b, a)[0]['verdict'], 'trial_current')

    def test_neither_and_attributes_are_not_passes(self):
        a, b, offset, _ = self.fixture()
        a[offset] = 193
        self.assertEqual(compare(a, b)[0]['verdict'], 'neither_current')
        b[offset+1] = 1
        self.assertEqual(compare(a, b)[0]['verdict'], 'unsupported')

    def test_different_source_and_short_snapshot_rejected(self):
        a, b, _, index = self.fixture()
        b[0x12000+index] = 194
        with self.assertRaises(ValueError):
            compare(a, b)
        with self.assertRaises(ValueError):
            compare(a[:100], b)
