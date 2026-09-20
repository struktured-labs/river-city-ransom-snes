import unittest
from tools.audit_alley_entry_work import return_index, prepare_phases


class AlleyEntryWorkTests(unittest.TestCase):
    def test_nested_return_skipped(self):
        rows=[dict(s=500,opcode=0),dict(s=498,opcode=0x60),dict(s=500,opcode=0),
              dict(s=500,opcode=0x60),dict(s=502,opcode=0)]
        self.assertEqual(return_index(rows,0,0x60),4)

    def test_interrupt_stack_wrap(self):
        rows=[dict(s=511,opcode=0),dict(s=511,opcode=0x40),dict(s=258,opcode=0)]
        self.assertEqual(return_index(rows,0,0x40),2)

    def test_long_bridge_skips_inner_short_return(self):
        rows=[dict(s=500,opcode=0),dict(s=498,opcode=0x60),dict(s=500,opcode=0),
              dict(s=500,opcode=0x6b),dict(s=503,opcode=0)]
        self.assertEqual(return_index(rows,0,0x6b),4)

    def test_bad_or_missing_stack_restore_rejected(self):
        with self.assertRaises(ValueError):
            return_index([dict(s=500,opcode=0),dict(s=500,opcode=0x60),dict(s=501,opcode=0)],0,0x60)
        with self.assertRaises(ValueError):
            return_index([dict(s=500,opcode=0),dict(s=498,opcode=0x60)],0,0x60)

    def test_phases_partition_elapsed_time(self):
        labels=dict(prepare_palette=1,prepare_sprites=2,prepare_tail=3,prepare_chr=4)
        rows=[dict(pc=0xc00000+i,clock=i*17) for i in range(6)]
        phases=prepare_phases(rows,0,5,labels)
        self.assertEqual(sum(p['elapsed_clocks'] for p in phases),85)
        self.assertEqual([p['name'] for p in phases],['rows',*labels])

    def test_incomplete_or_duplicate_phase_rejected(self):
        labels=dict(prepare_palette=1,prepare_sprites=2,prepare_tail=3,prepare_chr=4)
        for addresses in ([0,1,2,3,5,6],[0,1,1,2,3,4,6],[0,2,1,3,4,6]):
            rows=[dict(pc=0xc00000+v,clock=i*17) for i,v in enumerate(addresses)]
            with self.assertRaises(ValueError):
                prepare_phases(rows,0,len(rows)-1,labels)
