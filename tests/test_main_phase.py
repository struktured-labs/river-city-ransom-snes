import unittest
from tools.check_main_phase import STABLE,eligible
from tools.audit_nes_main_phase import pair


class MainPhaseTests(unittest.TestCase):
    def test_guard_exclusions(self):
        self.assertTrue(eligible(STABLE))
        for address,value in ((0x100,0),(0x107,128),(0x3f,32),(0x3e,2),(0x3e,128),
            (0x692,3),(0x1ca0,1),(0x1c0a,1),(0x1c83,1),(0x1ce0,1),(0x1ce1,1),
            (0x1ceb,0),(0x1c20,0)):
            with self.subTest(address=address):self.assertFalse(eligible({**STABLE,address:value}))

    def event(self,event,frame,clock,stack):
        row=['0']*50;row[:4]=list(map(str,(frame,20,clock,event)));row[12]=str(stack)
        return row

    def test_nes_pair_and_censored_boundary(self):
        rows=[self.event(1,9,1,253),self.event(0,10,2,255),self.event(2,10,3,255),self.event(1,11,4,253)]
        values,censored=pair(rows)
        self.assertEqual(values[0]['frame_span'],1)
        self.assertEqual(censored[0]['kind'],'leading camera')
        rows.append(self.event(1,11,5,248))
        values,censored=pair(rows)
        self.assertEqual(len(values),1)
        self.assertEqual(censored[-1]['kind'],'camera outside matched main')

    def test_duplicate_start_and_wrong_stack_rejected(self):
        for rows in ([self.event(0,10,1,255),self.event(0,12,2,255)],
                     [self.event(0,10,1,255),self.event(2,10,2,255),self.event(1,11,3,255)]):
            with self.assertRaises(ValueError):pair(rows)
