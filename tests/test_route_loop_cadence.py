import unittest
from tools.audit_route_loop_cadence import nes_pair,measure,stable_room


class RouteLoopCadenceTests(unittest.TestCase):
    def event(self,event,frame,tick=0,stack=250):
        r=['0']*50
        for i,v in ((0,frame),(2,frame*10+event),(3,event),(6,tick),(12,stack)):r[i]=str(v)
        return r

    def fixture(self):
        rows=[];loops=[]
        for room in range(4):
            ram=bytearray(2048);ram[0x42]=room;ram[0x100]=192;ram[0x692]=4
            for i in range(128):rows.append(dict(game_ram_hex=ram.hex(),frame=len(rows)+1))
            for i in range(64):
                f=room*128+2*i+1
                loops.append(dict(start=dict(frame=f,clock=f*100),input=dict(frame=f),
                    finish=dict(frame=f+1),nmi_advances=2))
        return loops,rows

    def test_nes_tick_clear_and_complete_iteration(self):
        loops,edges=nes_pair([self.event(0,1,2),self.event(1,1),self.event(2,2,2)])
        self.assertEqual(loops[0]['nmi_advances'],2);self.assertFalse(edges)

    def test_missing_input_reset_stack_and_restarted_loop_fail(self):
        variants=([self.event(0,1),self.event(2,2,2)],
            [self.event(0,1),self.event(1,1,1)],
            [self.event(0,1),self.event(1,1,stack=248)],
            [self.event(0,1),self.event(0,2)])
        for events in variants:
            with self.assertRaises(ValueError):nes_pair(events)

    def test_all_four_rooms_required_with_fixed_minimum(self):
        loops,rows=self.fixture();result=measure(loops,rows)
        self.assertTrue(result['sampled_two_tick_cadence'])
        self.assertEqual([len(v['iterations']) for v in result['rooms'].values()],[64]*4)
        self.assertFalse(measure(loops[:-1],rows)['sampled_two_tick_cadence'])

    def test_extra_tick_is_failure_not_excluded(self):
        loops,rows=self.fixture();loops[0]['nmi_advances']=3
        result=measure(loops,rows)
        self.assertFalse(result['sampled_two_tick_cadence'])
        self.assertEqual(len(result['rooms']['0']['off_cadence_iterations']),1)
        self.assertFalse(result['excluded'])

    def test_irregular_start_not_hidden_by_two_tick_completion(self):
        loops,rows=self.fixture();loops[1]['start']['frame']+=1
        result=measure(loops,rows)
        self.assertFalse(result['sampled_two_tick_cadence'])
        self.assertEqual(len(result['rooms']['0']['off_cadence_starts']),2)

    def test_paused_frame_excludes_entire_loop_but_is_retained(self):
        loops,rows=self.fixture();ram=bytearray.fromhex(rows[1]['game_ram_hex']);ram[0x107]=128
        rows[1]['game_ram_hex']=ram.hex();result=measure(loops,rows)
        self.assertEqual(result['excluded'],[loops[0]])
        self.assertFalse(result['sampled_two_tick_cadence'])

    def test_mixed_room_or_transition_not_joined(self):
        _,rows=self.fixture()
        self.assertIsNone(stable_room([rows[0],rows[128]]))
        rows[0]['native']=dict(transition_state=1)
        self.assertIsNone(stable_room(rows[:2]))

    def test_censored_edges_retained(self):
        events=[self.event(2,1,2),self.event(0,2),self.event(1,2),self.event(2,3,2),self.event(0,4)]
        loops,edges=nes_pair(events)
        self.assertEqual(len(loops),1)
        self.assertEqual([e['kind'] for e in edges],['leading completion','trailing iteration'])
