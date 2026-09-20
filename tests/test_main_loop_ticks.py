import unittest
from tools.audit_main_loop_ticks import pair


class MainLoopTickTests(unittest.TestCase):
    points={0:0x2990,1:0xf282,2:0xf2da}

    def event(self,event,frame,clock,nmi):
        return list(map(str,[event,frame,128,0,clock]))+[
            f'{0xc10000+self.points[event]:06x}']+list(map(str,[nmi,192,0,0,3,0,0,0,0,128]))

    def test_two_ticks_and_counter_wrap(self):
        rows=[self.event(0,1,1,65535),self.event(1,1,2,65535),self.event(2,2,3,1)]
        loops,censored=pair(rows,self.points,1,2)
        self.assertEqual(loops[0]['nmi_advances'],2)
        self.assertFalse(censored)

    def test_overrun_not_hidden(self):
        rows=[self.event(0,1,1,0),self.event(1,1,2,0),self.event(2,4,3,3)]
        self.assertEqual(pair(rows,self.points,1,4)[0][0]['nmi_advances'],3)

    def test_missing_input_and_duplicate_start_rejected(self):
        for events in ((0,2),(0,0),(1,2)):
            with self.assertRaises(ValueError):
                pair([self.event(e,1,i+1,0) for i,e in enumerate(events)],self.points,1,2)

    def test_censored_edges_retained(self):
        rows=[self.event(e,1,i+1,0) for i,e in enumerate((2,0,1,2,0))]
        _,censored=pair(rows,self.points,1,2)
        self.assertEqual([r['kind'] for r in censored],['leading completion','trailing iteration'])
