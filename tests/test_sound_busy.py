import unittest
from tools.audit_sound_busy import parse

def event(kind,tick,pc,op,stack=475):
    return [str(kind),'3276','81','900',str(tick),pc,op,'5','4','1',str(stack),'0','0','2876','192','0','0','0']

class SoundBusyTest(unittest.TestCase):
    def test_accepted_and_busy(self):
        enter=event(0,100,'c68146','2c');end=event(2,200,'c6819a','60')
        accepted=event(1,140,'c6814b','a2')
        self.assertTrue(parse([enter,end])['calls'][0]['busy_return'])
        self.assertFalse(parse([enter,accepted,end])['calls'][0]['busy_return'])

    def test_censored_nested_and_wrong_stack(self):
        enter=event(0,100,'c68146','2c');end=event(2,200,'c6819a','60')
        for rows in ([enter],[end],[enter,enter,end],[enter,event(2,200,'c6819a','60',474)]):
            with self.assertRaises(ValueError):parse(rows)
