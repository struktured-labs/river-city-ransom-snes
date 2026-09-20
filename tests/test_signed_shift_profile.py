import unittest

from tools.audit_signed_shift_game import shift_cost
from tools.build_signed_shift_trial import ADDRESS, ORIGINAL


class SignedShiftProfileTests(unittest.TestCase):
    def fixture(self):
        image=bytearray(2097152)
        image[0x10000+ADDRESS:0x10000+ADDRESS+17]=ORIGINAL
        pcs=(0xc3b9,0xc3bb,0xc3c8,0xc3bb,0xc3ca,
             0xc395,0xc3bb,0xc3c8,0xc3ca,0xc3d0)
        rows=[dict(pc=0xc10000+pc,opcode=image[0x10000+pc],clock=i*10,s=500)
              for i,pc in enumerate(pcs)]
        return image,rows

    def test_mid_loop_entry_is_a_separate_complete_call(self):
        image,rows=self.fixture()
        result=shift_cost(rows,0,len(rows)-1,image)
        self.assertEqual([r['clocks'] for r in result['calls']],[40,20])
        self.assertEqual(result['inclusive_clocks'],60)
        self.assertEqual(result['own_instruction_clocks'],60)

    def test_incomplete_or_changed_execution_rejected(self):
        image,rows=self.fixture()
        with self.assertRaises(ValueError):shift_cost(rows,0,8,image)
        rows[8]['s']+=1
        with self.assertRaises(ValueError):shift_cost(rows,0,len(rows)-1,image)
        image,rows=self.fixture();rows[1]['opcode']^=1
        with self.assertRaises(ValueError):shift_cost(rows,0,len(rows)-1,image)
