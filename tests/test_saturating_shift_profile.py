import unittest

from tools.audit_saturating_shift_game import helper_cost
from tools.build_saturating_shift_trial import ADDRESS, HELPER, HOOK


class SaturatingShiftProfileTests(unittest.TestCase):
    def fixture(self):
        image = bytearray(2097152)
        image[0x10000+ADDRESS:0x10000+ADDRESS+17] = HOOK
        image[0x10000+HELPER:0x10000+HELPER+64] = b'\xea'*64
        pcs = (0xc395,ADDRESS+2,HELPER,HELPER+2,ADDRESS+17,
               ADDRESS,ADDRESS+2,HELPER,ADDRESS+17,0xc3d0)
        rows = [dict(pc=0xc10000+pc,opcode=image[0x10000+pc],clock=i*10,s=500)
                for i,pc in enumerate(pcs)]
        return image,rows

    def test_direct_and_initial_entries_include_helper_cost(self):
        image,rows = self.fixture()
        result = helper_cost(rows,0,len(rows)-1,image)
        self.assertEqual([c['clocks'] for c in result['calls']],[30,30])
        self.assertEqual(result['own_instruction_clocks'],60)
        self.assertEqual(result['inclusive_clocks'],60)

    def test_truncation_and_stack_mismatch_rejected(self):
        image,rows = self.fixture()
        with self.assertRaises(ValueError):
            helper_cost(rows,0,8,image)
        rows[4]['s'] += 1
        with self.assertRaises(ValueError):
            helper_cost(rows,0,len(rows)-1,image)

    def test_changed_helper_opcode_rejected(self):
        image,rows = self.fixture()
        rows[2]['opcode'] ^= 1
        with self.assertRaises(ValueError):
            helper_cost(rows,0,len(rows)-1,image)
