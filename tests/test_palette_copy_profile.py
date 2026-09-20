import unittest
from tools.audit_room_load_profile import palette_copy_sections


class PaletteCopyProfileTests(unittest.TestCase):
    def rows(self):
        return [dict(frame=10,line=0,cycle=0,clock=x*100,pc=0xc7e477,
                     opcode=0xbd,x=x,y=0,a=0,s=500) for x in range(32)]+[
            dict(frame=10,line=0,cycle=0,clock=3200,pc=0xc7e482,
                 opcode=0xa9,x=32,y=0,a=0,s=500)]

    def test_exact_32_byte_loop(self):
        self.assertEqual(palette_copy_sections(self.rows(),10)[0]['cost']['master_clocks'],3200)

    def test_truncated_loop(self):
        with self.assertRaisesRegex(ValueError,'Truncated'):
            palette_copy_sections(self.rows()[:-1],10)

    def test_missing_byte(self):
        rows=self.rows();del rows[16]
        with self.assertRaisesRegex(ValueError,'sequence'):
            palette_copy_sections(rows,10)

    def test_wrong_return_stack(self):
        rows=self.rows();rows[-1]['s']=501
        with self.assertRaisesRegex(ValueError,'Truncated'):
            palette_copy_sections(rows,10)

    def test_wrong_load_opcode(self):
        rows=self.rows();rows[12]['opcode']=0xad
        with self.assertRaisesRegex(ValueError,'sequence'):
            palette_copy_sections(rows,10)
