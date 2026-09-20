import unittest
from pathlib import Path
from tools.check_hidden_dma import retirement
from tools.build_native import build


class HiddenRowRunTests(unittest.TestCase):
    def test_exhausted_batch_skips_following_unready_slot(self):
        selected,budget,cursor=retirement(1,False,0,127,True,31)
        self.assertEqual(selected,[127]+list(range(31)))
        self.assertEqual((budget,cursor),(0,32))

    def test_initially_empty_budget_does_not_scan(self):
        self.assertEqual(retirement(0,False,2048,0,True,0),([],0,0))

    def test_run_respects_wrap_hole_and_byte_budget(self):
        selected,budget,cursor=retirement(2,True,0,127,True,31)
        self.assertEqual(selected,[127]+list(range(31))+list(range(32,64)))
        self.assertEqual((budget,cursor),(0,64))

    def test_unvalidated_format_combination_rejected(self):
        with self.assertRaisesRegex(ValueError,'interleaved staging'):
            build(Path('missing'),[],Path('unused'),experimental_planar_rows=True,experimental_hidden_row_run=True)
        with self.assertRaisesRegex(ValueError,'not both'):
            build(Path('missing'),[],Path('unused'),experimental_planar_rows=True,experimental_fused_alias_rows=True)
