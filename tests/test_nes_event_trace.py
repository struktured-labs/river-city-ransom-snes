import unittest
from tools.nes_event_trace import validate


class NesEventTests(unittest.TestCase):
    def row(self,frame=20,clock=100,event=0,pc='f27d'):
        return list(map(str,(frame,240,clock,event)))+[pc]+['0']*45

    def test_valid_points(self):
        r=validate([self.row(),self.row(clock=101,event=1,pc='e2b1')],20,30,30,{'0':'f27d','1':'e2b1'})
        self.assertEqual(r['records'],2)

    def test_stale_window_wrong_pc_and_missing_point(self):
        for rows,points in (([self.row(frame=19)],{'0':'f27d'}),
                            ([self.row(pc='f282')],{'0':'f27d'}),
                            ([self.row()],{'0':'f27d','1':'e2b1'})):
            with self.assertRaises(ValueError):validate(rows,20,30,30,points)

    def test_duplicate_unordered_and_malformed(self):
        for rows in ([self.row(),self.row()], [self.row(),self.row(clock=99)], [self.row()[:-1]]):
            with self.assertRaises(ValueError):validate(rows,20,30,30,{'0':'f27d'})
