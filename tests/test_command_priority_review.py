import unittest
from tools.review_command_priority import commands

def row(t,incoming,outgoing):return [str(t),'0477','3f','0','0','0','240',str(incoming),str(outgoing),'0','0']

class CommandTest(unittest.TestCase):
    def test_complete(self):
        r=commands([row(1,0,125),row(2,215,125),row(8,215,215)])
        self.assertEqual(r[0]['spc_clocks'],6)
        self.assertEqual(sum(r[0]['clocks_by_pc'].values()),6)

    def test_missing_and_censored_rejected(self):
        for rows in ([row(1,215,125),row(8,215,215)],
                     [row(1,0,125),row(2,215,125)],
                     [row(1,0,125),row(1,215,215)],[]):
            with self.assertRaises(ValueError):commands(rows)
