import unittest

from tools.audit_park_instructions import parse, section


class InstructionTimingTests(unittest.TestCase):
    def rows(self):
        return [['10','240','0','100','c12100','a9','0','0','0','500'],
                ['10','240','20','120','c22100','ea','0','0','0','500'],
                ['10','240','40','140','c02100','ea','0','0','0','500'],
                ['10','240','60','160','c7fa54','20','0','0','0','500']]

    def test_runtime_aggregation_does_not_merge_producer_bank(self):
        summary, selected = section(parse(self.rows(),10,10),100,160)
        self.assertEqual(summary['master_clocks'],60)
        self.assertEqual(summary['instructions'],3)
        self.assertEqual(summary['top_instruction_elapsed'],[
            dict(pc='runtime:2100',clocks=40),dict(pc='c02100',clocks=20)])
        self.assertEqual(len(selected),4)

    def test_reject_partial_stage(self):
        rows=parse(self.rows(),10,10)
        for start,end in ((99,160),(100,159),(101,160)):
            with self.assertRaisesRegex(ValueError,'boundary'):
                section(rows,start,end)

    def test_reject_clock_reset_and_bad_width(self):
        rows=self.rows();rows[2][3]='1'
        with self.assertRaisesRegex(ValueError,'increasing'):
            parse(rows,10,10)
        rows=self.rows();rows[0].pop()
        with self.assertRaisesRegex(ValueError,'ten-column'):
            parse(rows,10,10)

    def test_reject_out_of_window_and_invalid_opcode(self):
        with self.assertRaisesRegex(ValueError,'bounds'):
            parse(self.rows(),11,12)
        rows=self.rows();rows[0][5]='100'
        with self.assertRaisesRegex(ValueError,'bounds'):
            parse(rows,10,10)


if __name__=='__main__':
    unittest.main()
