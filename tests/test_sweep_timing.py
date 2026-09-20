import unittest
from tools.audit_sweep_timing import nes_events,bind_writes,next_event,reload_context


class SweepTimingTests(unittest.TestCase):
    def row(self,kind,clock=20,period=172,count=1):
        return [kind,'4',str(clock),'1','6','172',str(period),'148',str(count),'0','1']

    def test_actual_pitch_change(self):
        writes,changes,halves=nes_events([self.row('W',10),self.row('B'),self.row('H',period=182,count=2)])
        self.assertEqual(len(writes),1)
        self.assertEqual(changes[1][0]['before_period'],172)
        self.assertEqual(changes[1][0]['period'],182)
        self.assertEqual(len(halves[1]),1)

    def test_unchanged_half_frame_not_a_pitch_change(self):
        _,changes,_=nes_events([self.row('B'),self.row('H',count=2)])
        self.assertFalse(changes[1])

    def test_bad_pair_rejected(self):
        for rows in ([self.row('H')],[self.row('B')],
                     [self.row('B'),self.row('H',21)],
                     [self.row('B'),self.row('W'),self.row('H')]):
            with self.assertRaises(ValueError):nes_events(rows)

    def test_next_timer_boundary_excludes_change(self):
        events=[dict(clock=10),dict(clock=20)]
        self.assertIsNone(next_event(events,10,20))
        self.assertEqual(next_event(events,10,21),dict(clock=20))

    def test_completed_frame_is_before_write_frame(self):
        writes,_,_=nes_events([self.row('W')])
        rows=[['W','5','0','0','0','6','172','0000']]
        rows += [['P','5','0','0','0',str(i),'0','0000'] for i in range(23)]
        self.assertEqual(bind_writes(writes,rows)[0]['source_frame'],5)
        writes[0]['completed_frame']=5
        with self.assertRaises(ValueError):bind_writes(writes,rows)

    def split_case(self):
        low=dict(packet=6104,voice=1,clock=100,address=6,value=144,period=144)
        high=dict(packet=6104,voice=1,clock=200,address=7,value=0,period=153)
        change=dict(clock=150,before_period=144,period=153)
        return low,high,change

    def test_split_write_interleave_retained(self):
        low,high,change=self.split_case()
        result=reload_context(high,dict(period=144),[low,high],[change])
        self.assertEqual(result['classification'],'nes_half_frame_between_split_timer_writes')
        self.assertFalse(result['reload_period_matches'])
        self.assertEqual(result['packet_writes'],[low,high])
        self.assertEqual(result['changes_between_last_timer_writes'],[change])

    def test_interleave_requires_exact_observed_chain(self):
        low,high,change=self.split_case()
        for events in ([],[dict(change,clock=99)],[dict(change,clock=201)],
                       [dict(change,before_period=143)],[dict(change,period=154)]):
            result=reload_context(high,dict(period=144),[low,high],events)
            self.assertEqual(result['classification'],'unexplained_reload_difference')

    def test_interleave_requires_raw_timer_match(self):
        low,high,change=self.split_case()
        result=reload_context(high,dict(period=145),[low,high],[change])
        self.assertEqual(result['classification'],'unexplained_reload_difference')

    def test_matching_reload_not_classified_as_interleave(self):
        low,high,change=self.split_case()
        result=reload_context(high,dict(period=153),[low,high],[change])
        self.assertEqual(result['classification'],'matching_reload')
        self.assertTrue(result['reload_period_matches'])
