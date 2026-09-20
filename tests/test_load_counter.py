import copy
import unittest
from tools.audit_load_counter import compare_load, signature, phase_gate, parse
from tools.audit_combat_loops import PHASES


class LoadCounterTests(unittest.TestCase):
    def test_actual_event_abis_and_counter_reset_mutants(self):
        for system in ('nes','snes'):
            points={0:0xf27d if system=='nes' else 0x31f7,1:0xf282,2:0xf2da,3:0xe05c,4:0xe05f}
            image=bytearray(0x200000);records=[]
            opcodes={0:'a900' if system=='nes' else 'a9018de11ca9008d0b01',
                1:'2031f7',2:'ee2b05',3:'8d0b01',4:'a9c0'}
            for frame,event,tick,stack in ((10,0,2,255),(10,1,0,255),(23,3,1,251),(23,4,0,251),(25,2,2,255)):
                row=['0']*(50 if system=='nes' else 56)
                pc=points[event] if system=='nes' else 0xc10000+points[event]
                offset=16+0x10000+pc if system=='nes' else pc&0x3fffff
                data=bytes.fromhex(opcodes[event]);image[offset:offset+len(data)]=data
                row[0]=str(frame);row[3]=str(event);row[4]=f'{pc:x}';row[6]=str(tick)
                row[12 if system=='nes' else 13]=str(stack);records.append(row)
            loops,_=parse(records,system,points,image)
            self.assertEqual(loops[0]['frame_span'],15)
            self.assertEqual(loops[0]['finish']['game_tick'],2)
            bad=copy.deepcopy(records);bad[3][6]='1'
            with self.assertRaises(ValueError):parse(bad,system,points,image)
            with self.assertRaises(ValueError):parse(records[:1]+records[2:],system,points,image)
            with self.assertRaises(ValueError):parse(records,system,points,bytes(len(image)))

    def loop(self,start=100,span=15):
        events=[dict(frame=start+offset,event=kind,game_tick=tick) for offset,kind,tick in
                ((0,0,2),(0,1,0),(13,3,1),(13,4,0),(span,2,2))]
        return dict(start=events[0],finish=events[-1],events=events,frame_span=span)

    def test_elapsed_time_not_replaced_by_reset_counter(self):
        a=self.loop();b=self.loop(200)
        self.assertTrue(all(compare_load(a,b).values()))
        late=self.loop(200,16)
        self.assertEqual(late['finish']['game_tick'],2)
        self.assertFalse(compare_load(a,late)['elapsed_frames_no_slower'])
        bad=copy.deepcopy(b);bad['events'][3]['game_tick']=1
        self.assertFalse(compare_load(a,bad)['counter_sequence_exact'])
        self.assertEqual(signature(a),signature(b))

    def test_phase_gate_keeps_every_unmatched_deadline(self):
        rows=[];loops=[]
        for phase in PHASES:
            start=len(rows)+1
            rows.extend(dict(frame=start+i,phase=phase) for i in range(6))
            for i in (0,2,4):
                loops.append(dict(start=dict(frame=start+i),finish=dict(frame=start+i+2,game_tick=2),frame_span=2))
        self.assertTrue(all(v['passed'] for v in phase_gate(loops,rows,(-1,-1)).values()))
        bad=copy.deepcopy(loops);bad[2]['frame_span']=3
        self.assertFalse(all(v['passed'] for v in phase_gate(bad,rows,(-1,-1)).values()))
        bad=copy.deepcopy(loops);bad.pop(1)
        self.assertFalse(all(v['passed'] for v in phase_gate(bad,rows,(-1,-1)).values()))
