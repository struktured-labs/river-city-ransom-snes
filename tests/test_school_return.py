import unittest

from tools.review_combat_checkpoints import transition
from tools.audit_school_return import first_return
from tools.school_return_campaign import buttons,reached,validate_completion,installed,NAME
from tools import benchmark_capture as benchmark


class SchoolReturnTests(unittest.TestCase):
    def ram(self,room):
        r=bytearray(2048);r[0x42]=room;r[0x100]=0xc0
        return r

    def test_input_only_direction_and_stop(self):
        r=self.ram(0)
        self.assertEqual(buttons('school-to-alley',r,0),['Right','A','B'])
        self.assertEqual(buttons('school-to-alley',r,4),['Right'])
        self.assertEqual(buttons('alley-to-school',self.ram(1),4),['Left'])
        self.assertEqual(buttons('alley-to-school',r,0),[])
        r[0x3f]=0x20
        self.assertFalse(reached('alley-to-school',r))
        self.assertEqual(buttons('school-to-alley',r,0),[])

    def test_first_three_observations_required(self):
        samples=[self.ram(1),self.ram(0),self.ram(0),self.ram(0)]
        validate_completion('alley-to-school',samples,3600,True)
        with self.assertRaises(ValueError):
            validate_completion('alley-to-school',samples+[self.ram(0)],3600,True)
        with self.assertRaises(ValueError):
            validate_completion('alley-to-school',samples,3600,False)

    def test_dispatch_restored(self):
        old=benchmark.scenario_for;policy=benchmark.waypoint_policy
        with installed():
            phases=benchmark.scenario_for(NAME)
            self.assertEqual(phases[-1]['name'],'school_settle')
            self.assertEqual([p['waypoint'] for p in phases if 'waypoint' in p],['school-to-alley','alley-to-school'])
        self.assertIs(benchmark.scenario_for,old);self.assertIs(benchmark.waypoint_policy,policy)

    def rows(self):
        rows=[]
        for i in range(100):
            r=self.ram(1 if i<2 else 0);r[0x52b]=i//2
            n=bytearray(1024);n[0x21]=24 if i<2 or i>=20 else 0
            rows.append(dict(frame=4000+i,game_ram_hex=r.hex(),native_ram_hex=n.hex()))
        return rows

    def test_first_school_transition_and_counter(self):
        d=transition(self.rows())
        self.assertEqual((d['room'],d['change_frame'],d['off_frame'],d['enable_frame']),(0,4002,4002,4020))
        self.assertEqual(d['off_cadence_completion_intervals'],[])

    def test_missing_edges_truncation_and_counter_reset_refused(self):
        with self.assertRaises(ValueError):transition(self.rows()[2:])
        with self.assertRaises(ValueError):transition(self.rows()[:55])
        rows=self.rows();ram=bytearray.fromhex(rows[30]['game_ram_hex']);ram[0x52b]=0
        rows[30]['game_ram_hex']=ram.hex()
        with self.assertRaises(ValueError):transition(rows)

    def test_return_oracle_uses_real_room_edge(self):
        rows=self.rows()
        for row in rows:row['native']=dict(ppu_mask=bytes.fromhex(row['native_ram_hex'])[0x21])
        index,anchors=first_return(rows)
        self.assertEqual(index,20)
        self.assertEqual(anchors['room_change_frame'],4002)
        with self.assertRaises(ValueError):first_return(rows[2:])
        with self.assertRaises(ValueError):first_return(rows[:55])

    def test_return_oracle_cannot_choose_later_room_entry(self):
        rows=self.rows()
        for row in rows:row['native']=dict(ppu_mask=bytes.fromhex(row['native_ram_hex'])[0x21])
        # First room0 entry never enables, then room1/0 again; refuse the later
        # complete fade instead of silently reporting the favorable entry.
        for i in range(20,60):rows[i]['native']['ppu_mask']=0
        for i in range(35,45):
            ram=bytearray.fromhex(rows[i]['game_ram_hex']);ram[0x42]=1
            rows[i]['game_ram_hex']=ram.hex()
        with self.assertRaises(ValueError):first_return(rows)
