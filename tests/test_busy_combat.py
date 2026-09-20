import unittest

from tools.audit_busy_combat import classify,measure
from tools.audit_route_loop_cadence import stable_room


class BusyCombatTests(unittest.TestCase):
    def rows(self):
        ram = bytearray(2048)
        ram[0x100]=0xc0;ram[0x692]=4
        return [dict(frame=f,game_ram_hex=ram.hex(),native=dict(transition_state=0)) for f in range(1,5)]

    def test_busy_interrupt_does_not_disappear_from_speed_denominator(self):
        rows=self.rows();ram=bytearray.fromhex(rows[1]['game_ram_hex']);ram[0x107]=128
        rows[1]['game_ram_hex']=ram.hex()
        self.assertIsNone(stable_room(rows))
        self.assertEqual(classify(rows),dict(room=0,busy_frames=[2],exclusions=[]))
        loops=[dict(start=dict(frame=f,clock=f*100,nmi=f),finish=dict(frame=f+1),nmi_advances=2)
               for f in (1,4)]
        result=measure(dict(iterations=loops,other_iterations=[]),rows)
        self.assertFalse(result['passed'])
        self.assertEqual(result['frame_histogram'],{3:1})
        self.assertEqual(result['off_cadence'][0]['context']['busy_frames'],[2])

    def test_other_stability_requirements_remain(self):
        for address,value in ((0x100,0),(0x3f,32),(0x3e,128),(0x692,3),(0x42,1)):
            rows=self.rows();ram=bytearray.fromhex(rows[1]['game_ram_hex']);ram[address]=value
            rows[1]['game_ram_hex']=ram.hex()
            self.assertIsNone(classify(rows)['room'])
            self.assertTrue(classify(rows)['exclusions'])
        rows=self.rows();rows[1]['native']['transition_state']=1
        self.assertIsNone(classify(rows)['room'])
        rows=self.rows();rows[1]['game_ram_hex']='00'
        with self.assertRaises(ValueError):classify(rows)
