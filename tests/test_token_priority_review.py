import unittest
from tools.review_token_priority import token_events,cpu_windows
from tools.build_receiver_token_priority import CODE,ORIGIN

def row(t,i,o):return [str(t),'3530','e4','0','22','0','240',str(i),str(o),'1','0']

class TokenPriorityTest(unittest.TestCase):
    def test_actual_branch_targets(self):
        self.assertEqual(len(CODE),16)
        self.assertEqual(ORIGIN+4+CODE[3],ORIGIN+13)
        self.assertEqual(ORIGIN+8+CODE[7],ORIGIN+11)
        self.assertEqual(ORIGIN+13+CODE[12]-256,ORIGIN)
        self.assertEqual(CODE[8:11],bytes.fromhex('3f8432'))
        self.assertEqual(CODE[13:],bytes.fromhex('5fe132'))

    def test_retains_pending_timer_span(self):
        rows=[row(1,20,20),row(2,22,20),row(381,22,22)]
        self.assertEqual(token_events(rows)[0]['clocks'],379)
        with self.assertRaises(ValueError):token_events(rows[:-1])
        with self.assertRaises(ValueError):token_events([rows[0],rows[0]])
        with self.assertRaises(ValueError):cpu_windows([])
