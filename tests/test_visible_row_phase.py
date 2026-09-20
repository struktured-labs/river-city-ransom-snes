import inspect
from pathlib import Path
import unittest
from tools.build_native import build
from tools.check_visible_row_phase import STABLE,budget_for


class VisibleRowPhaseTests(unittest.TestCase):
    def test_opt_in(self):
        self.assertFalse(inspect.signature(build).parameters['experimental_visible_row_phase'].default)
        with self.assertRaisesRegex(ValueError,'Visible row phase'):
            build(Path('unused'),[],Path('unused'),experimental_visible_row_phase=True)

    def test_exact_ticks(self):
        self.assertEqual([budget_for(STABLE+(x,)) for x in (0,1,2,3,255)],[2,4,0,2,2])

    def test_pause_and_transition_keep_rows(self):
        for i,v in ((1,128),(2,32),(3,2),(4,3),(5,2)):
            state=list(STABLE+(2,));state[i]=v
            self.assertEqual(budget_for(state),2)
        self.assertEqual(budget_for((0,0,0,0,4,0,2)),4)
