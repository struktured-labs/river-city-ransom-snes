import unittest
from tools.audit_audio_irq_returns import returns


def sample(stack=0x1fc):
    common=dict(a=0xabcd,x=0x78,y=0xbc,s=stack)
    return [dict(common,pc=0xc1791b,opcode=8,clock=1),
            dict(common,pc=0xc7f1d8,opcode=0x40,clock=10),
            dict(common,pc=0xc7f2c9,opcode=0xea,clock=15,s=0x100+((stack+3)&255))]


class AudioIrqReturnTests(unittest.TestCase):
    def test_intact_and_page_one_wrap(self):
        for stack in (0x1fc,0x1fe,0x1ff):
            self.assertTrue(returns(sample(stack))['passed'])

    def test_hidden_b_and_each_register(self):
        for index in (1,2):
            for field in ('a','x','y','s'):
                rows=sample();rows[index][field]^=256 if field=='a' else 1
                self.assertFalse(returns(rows)['passed'])

    def test_censored_and_reentrant_returns(self):
        for rows in ([],sample()[:1],sample()[:2],[sample()[0],sample()[0],*sample()[1:]]):
            with self.assertRaises(ValueError):returns(rows)

    def test_not_an_rti(self):
        rows=sample();rows[1]['opcode']=0xea
        with self.assertRaises(ValueError):returns(rows)
