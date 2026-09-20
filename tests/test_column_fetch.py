import unittest

from tools.check_column_fetch import expected,inputs


class ColumnFetchTests(unittest.TestCase):
    def test_matrix_covers_counts_columns_and_x(self):
        rows=inputs()
        self.assertEqual(len(rows),5120)
        for index in range(3):self.assertEqual({r[index] for r in rows},set(range(256)))

    def test_normal_count_and_ring_wrap(self):
        r=expected(bytes((8,7,63,0x7c,0x55,0xf0,0x3e,0)),0xc4)
        self.assertEqual(len(r),1024)
        self.assertEqual(r[0x21],48)
        self.assertEqual(r[512:522],bytes((48,0x55,19,7,0x7f,255,1,0x84,0,0)))

    def test_entry_count_wrap(self):
        r=expected(bytes((255,0,0,0x30,0,255,7,0)),0xc1)
        self.assertEqual(r[0x21],49)
        self.assertEqual(r[514],25)
        self.assertEqual(r[516]&3,1)

    def test_single_row_retains_negative_compare_flag(self):
        r=expected(bytes((250,255,255,0x30,0,255,7,0)),0xc8)
        self.assertEqual(r[512],252)
        self.assertEqual(r[514],0)
        self.assertTrue(r[516]&0x80)
