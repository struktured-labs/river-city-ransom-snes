import unittest

from tools.audit_main_work import measure


def row(pc,clock,stack=0x1fd,opcode=0xea):
    return dict(pc=pc,clock=clock,s=stack,opcode=opcode,frame=1,line=1,cycle=clock,a=0,x=0,y=0)


class MainWorkTests(unittest.TestCase):
    def test_call_matches_return_stack_and_retains_trailing(self):
        rows=[row(0xc7f282,0,opcode=0x20),row(0xc7f285,20,stack=0x1fb),
            row(0xc7f285,100),row(0xc7f299,110,opcode=0x20)]
        r=measure(rows,{})
        self.assertEqual(len(r['calls']),1)
        self.assertEqual(r['calls'][0]['elapsed_clocks'],100)
        self.assertEqual(len(r['censored']),1)

    def test_ordinary_nmi_is_separate_from_main_work(self):
        rows=[row(0xc7f299,0,opcode=0x20),row(0xc58000,20,stack=0x1fb),
            row(0x8100,40,stack=0x1f8),row(0xc7f1d8,90,stack=0x1f8,opcode=0x40),
            row(0xc58002,110,stack=0x1fb),row(0xc7f29c,150,opcode=0x20)]
        r=measure(rows,{40:0x8100})['calls'][0]
        self.assertEqual(r['ordinary_nmi_clocks'],70)
        self.assertEqual(r['outside_ordinary_nmi_clocks'],80)

    def test_changed_call_or_incomplete_interrupt_is_rejected(self):
        with self.assertRaises(ValueError):measure([row(0xc7f282,0)],{})
        rows=[row(0xc7f299,0,opcode=0x20),row(0x8100,40,stack=0x1f8),row(0xc7f29c,150)]
        with self.assertRaises(ValueError):measure(rows,{40:0x8100})
