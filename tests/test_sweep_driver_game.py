import unittest

from tools.audit_sweep_driver_game import metadata_events
from tools.analyze_spc_receive import compare


class LiveDriverGameTests(unittest.TestCase):
    def test_same_value_writes_reflag_and_last_frame_mode_wins(self):
        def row(kind,index,value):return [kind,'1','0','0','0',str(index),str(value),'c12345']
        rows=[row('W',1,0),row('W',23,128),row('W',23,0),row('P',20,65),row('P',22,0),
              row('W',1,0),row('P',20,1),row('P',22,0),row('P',20,0),row('P',22,0)]
        self.assertTrue(metadata_events(rows)['passed'])
        rows[6][-2]='0'
        self.assertFalse(metadata_events(rows)['passed'])

    def test_relocated_receiver_still_checks_instruction_identity(self):
        sent=[['P','1','0','0','0',str(i),'5','c08000'] for i in range(23)]
        pcs=(0x3333,0x3344)
        received=[[str(i),'5',f'{pcs[i&1]:04x}'] for i in range(23)]
        self.assertTrue(compare(sent,received,paired=True,receiver_pcs=pcs)['passed'])
        received[3][2]='3011'
        with self.assertRaises(ValueError):compare(sent,received,paired=True,receiver_pcs=pcs)
        with self.assertRaises(ValueError):compare(sent,received,receiver_pcs=pcs)
