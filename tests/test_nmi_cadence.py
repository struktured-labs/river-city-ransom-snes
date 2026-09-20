import unittest
from tools.audit_nmi_cadence import intervals
from tools.audit_park_spans import FRAME_CLOCKS


class NMICadenceTests(unittest.TestCase):
    def event(self,frame,event=0,**kw):
        return dict(event=event,frame=frame,line=240,clock=frame*FRAME_CLOCKS,
                    room=3,task=192,pause=0,guard=0,transition=0,**kw)

    def test_regular_and_missing_interrupt(self):
        self.assertEqual(intervals([self.event(1),self.event(2),self.event(3)])['late'],[])
        self.assertEqual(len(intervals([self.event(1),self.event(3)])['late']),1)

    def test_changed_producer_order_does_not_hide_interrupts(self):
        rows=[self.event(1),self.event(1,6),self.event(1,1),self.event(3)]
        self.assertEqual(len(intervals(rows)['late']),1)

    def test_transition_exclusion_retained(self):
        rows=[self.event(1),self.event(2),self.event(3),self.event(5)]
        rows[2]['transition']=1
        result=intervals(rows)
        self.assertEqual(result['intervals'],1)
        self.assertEqual(len(result['excluded_intervals']),2)

    def test_no_coverage_rejected(self):
        with self.assertRaises(ValueError):intervals([self.event(1)])
