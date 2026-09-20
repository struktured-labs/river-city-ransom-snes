import unittest
from tools.audit_deferred_phase import waits


class PhaseWaitTests(unittest.TestCase):
    def test_repeated_entry_is_one_wait(self):
        rows=[dict(pc=p,clock=t) for p,t in ((10,1),(15,2),(10,3),(20,5),(10,6),(20,8))]
        result=waits(rows,10,20)
        self.assertEqual([r['clocks'] for r in result],[4,2])
        self.assertEqual([r['iterations'] for r in result],[2,1])

    def test_missing_truncated_empty_and_bad_clocks_rejected(self):
        for rows in ([],[dict(pc=20,clock=1)],[dict(pc=10,clock=1)],
                [dict(pc=10,clock=2),dict(pc=20,clock=2)]):
            with self.assertRaises(ValueError):waits(rows,10,20)
