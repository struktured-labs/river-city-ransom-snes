import unittest
from tools.audit_alley_fade_schedule import nes_iterations


class AlleyFadeScheduleTests(unittest.TestCase):
    def events(self):
        rows=[]
        for i in range(8):
            r=['0']*50
            r[:5]=['100','12',str(1000+i*10),str(i),'e343' if i==6 else 'f293']
            r[12]=str(253 if i==6 else 255);rows.append(r)
        return rows

    def test_exact_call_sequence_and_stack(self):
        r=nes_iterations(self.events(),100,1)
        self.assertEqual(r[0]['main_to_fade_cpu_cycles'],60)

    def test_missing_or_reordered_boundary_rejected(self):
        for index in (1,5,6):
            rows=self.events();rows[index][3]='0'
            with self.assertRaises(ValueError):nes_iterations(rows,100,1)

    def test_wrong_stack_and_truncation_rejected(self):
        rows=self.events();rows[6][12]='255'
        with self.assertRaises(ValueError):nes_iterations(rows,100,1)
        with self.assertRaises(ValueError):nes_iterations(self.events()[:-1],100,1)
