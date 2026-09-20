import unittest

from tools.audit_driver_write_coalescing import corrupt_observed_final,group_nes,parse_writes,summarize
from tools.build_nes_apu_clock_core import transform


class DriverWriteCoalescing(unittest.TestCase):
    def test_write_bounds_and_clock_order(self):
        row=['1','10','812b','4004','240','192','1','0','0']
        self.assertEqual(parse_writes([row],1)[0]['register'],4)
        for index,value in ((0,'2'),(3,'4016'),(4,'256')):
            broken=list(row);broken[index]=value
            with self.assertRaises(ValueError):parse_writes([broken],1)
        earlier=list(row);earlier[1]='9'
        with self.assertRaises(ValueError):parse_writes([row,earlier],1)

    def test_wrapper_boundaries_and_transient_duration(self):
        ws=[dict(clock=c,register=4,value=v) for c,v in ((9,1),(12,0xf0),(20,0xf3),(31,2))]
        groups,outside=group_nes(ws,[dict(entry=dict(clock=10),returned=dict(clock=30))])
        self.assertEqual([w['clock'] for w in outside],[9,31])
        s=summarize(groups)
        self.assertEqual(s['changing_patterns'],[dict(register=4,values=[240,243],count=1)])
        self.assertEqual(s['zero_then_nonzero_constant_volume'][0]['clocks'],8)

    def test_same_value_reload_is_not_discarded(self):
        s=summarize([dict(driver=1,writes=[dict(register=3,value=7,clock=2),dict(register=3,value=7,clock=9)])])
        self.assertFalse(s['changing_register_groups'])
        self.assertEqual(len(s['repeated_side_effect_registers']),1)

    def test_exact_cpu_hook_guard(self):
        old='static INLINE void WrMemNorm(uint32_t A, uint8_t V) {\n    rcr_scroll_write(A, V);\n\tBWrite[A](A, V);\n}'
        self.assertIn('fceumm_apu_write_clock.inc',transform(old))
        for wrong in ('',old+old,old.replace('BWrite','OtherWrite')):
            with self.assertRaises(ValueError):transform(wrong)

    def test_mutation_requires_observed_initial_state(self):
        bus=[['P','1','0','0','0','0','0','c00000'],
             ['W','2','0','0','0','0','3','c00000'],
             ['P','2','0','0','0','0','3','c00000']]
        changed=corrupt_observed_final(bus)
        self.assertEqual(changed[0],bus[0])
        self.assertEqual(changed[2][6],'2')
        self.assertEqual(bus[2][6],'3')
        with self.assertRaises(ValueError):corrupt_observed_final(bus[:1])


if __name__=='__main__':unittest.main()
