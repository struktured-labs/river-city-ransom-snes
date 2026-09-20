import unittest

from tools.audit_hud_final_budget import measure


class FinalBudgetTests(unittest.TestCase):
    def fixture(self):
        rows = []
        def add(pc, x=0, opcode=0xea):
            rows.append(dict(frame=2472, line=253, cycle=len(rows)*30,
                             clock=10000+len(rows)*30, pc=pc, opcode=opcode,
                             a=1, x=x, y=23))
        add(0xc087e4)
        add(0xc0844f)
        add(0xc08460)
        for pc, size in ((0xc0849e,32),(0xc084b4,8),(0xc084ca,8),
                         (0xc084e0,8),(0xc084f6,8)):
            add(pc,size,0x8d)
            add(pc+3)
        return rows

    def test_complete_batch(self):
        report=measure(self.fixture())
        self.assertEqual(report['palette_bytes'],64)
        self.assertEqual(len(report['palette_transfers']),5)

    def test_missing_transfer_fails(self):
        rows=[r for r in self.fixture() if r['pc']!=0xc084ca]
        with self.assertRaises(ValueError): measure(rows)

    def test_wrong_size_fails(self):
        rows=self.fixture()
        next(r for r in rows if r['pc']==0xc084ca)['x']=64
        with self.assertRaises(ValueError): measure(rows)

    def test_skipped_final_batch_fails(self):
        rows=[r for r in self.fixture() if r['pc']!=0xc08460]
        with self.assertRaises(ValueError): measure(rows)

    def test_nonconsecutive_dma_end_fails(self):
        rows=self.fixture()
        next(r for r in rows if r['pc']==0xc084a1)['pc']=0xc084a2
        with self.assertRaises(ValueError): measure(rows)
