import unittest
from tools.audit_room_load_profile import interrupt_accounting


def row(clock,pc=0xc7f299,opcode=0xea,stack=0x1fd):
    return dict(clock=clock,pc=pc,opcode=opcode,s=stack,frame=100)


class RoomLoadAccountingTests(unittest.TestCase):
    def fixture(self):
        return [row(0),row(10,0x80fb,stack=0x1fa),row(50,0xc72f00,0x40,0x1fa),row(60),row(80)]

    def test_nmi_and_residual_partition_exact_elapsed(self):
        r=interrupt_accounting(self.fixture(),{10:0x80fb})
        self.assertEqual(r['ordinary_nmi_clocks'],50)
        self.assertEqual(r['outside_ordinary_nmi_clocks'],30)
        self.assertEqual(r['outside_nmi_instruction_elapsed'],[dict(pc='c7f299',clocks=30)])

    def test_no_interrupt_keeps_all_elapsed(self):
        r=interrupt_accounting([row(0),row(20)],{})
        self.assertEqual(r['outside_ordinary_nmi_clocks'],20)
        self.assertEqual(r['ordinary_nmi_clocks'],0)

    def test_missing_return_or_restored_stack_rejected(self):
        for rows in (self.fixture()[:3],self.fixture()[:3]+[row(60,stack=0x1fc)]):
            with self.assertRaises(ValueError):interrupt_accounting(rows,{10:0x80fb})

    def test_mismatched_or_nested_entry_rejected(self):
        for events in ({10:0x80fc},{10:0x80fb,50:0xc72f00}):
            with self.assertRaises(ValueError):interrupt_accounting(self.fixture(),events)

    def test_emulation_stack_wrap_is_validated(self):
        rows=[row(0,0x80fb,stack=0x1fe),row(20,0xc72f00,0x40,0x1fe),row(30,stack=0x101)]
        self.assertEqual(interrupt_accounting(rows,{0:0x80fb})['ordinary_nmi_clocks'],30)
