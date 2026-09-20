import unittest

from tools.audit_shift_fade_schedule import marks


class FadeBoundaryTests(unittest.TestCase):
    def fixture(self):
        return [dict(pc=0xc70000+pc,frame=101,line=i,cycle=0,clock=i*10)
                for i,pc in enumerate((0x3000,0xf293,0xe343,0xf2c9,0xf2c9,0xf2da))]

    def test_repeated_poll_is_collapsed_not_finish_or_reset(self):
        got=marks(self.fixture(),100,0x3000)
        self.assertEqual([r['name'] for r in got],['reset','first-call','fade','wait','finish'])
        self.assertTrue(all(r['offset']==1 for r in got))

    def test_wrong_bank_and_missing_boundary_rejected(self):
        rows=self.fixture();rows[-1]['pc']=0xc0f2da
        with self.assertRaises(ValueError):marks(rows,100,0x3000)
        with self.assertRaises(ValueError):marks(self.fixture()[:-1],100,0x3000)
