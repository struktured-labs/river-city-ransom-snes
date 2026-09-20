import unittest
from fractions import Fraction
from tools.build_dc_pulse_trial import ORIGINAL, decode, patch
from tools.build_dc_pulse_control import patch as wrong_gain
from tools.audit_dc_pulse_trial import dsp_equal, levels


class DcPulseTests(unittest.TestCase):
    def engine(self):
        data=bytearray(0x900)
        for at,reg in ((0x2c,7),(0x32,0x17),(0x147,7),(0x215,0x17)):
            data[at:at+6]=bytes((0x8f,reg,0xf2,0x8f,31,0xf3))
        for i,block in enumerate(ORIGINAL):data[0x859+9*i:0x859+9*(i+1)]=bytes.fromhex(block)
        return bytes(data)

    def test_affine_centering_preserves_phase_duty_and_span(self):
        old=self.engine();new,detail=patch(old)
        self.assertEqual(sum(a!=b for a,b in zip(old,new)),32)
        for i in range(4):
            a=decode(old[0x859+9*i:0x859+9*(i+1)])
            b=decode(new[0x859+9*i:0x859+9*(i+1)])
            self.assertEqual(sum(b),0)
            self.assertEqual([Fraction(v) for v in b],[(v-Fraction(sum(a),16))*Fraction(8,9) for v in a])
        self.assertEqual(len(detail['changes']),8)

    def test_all_four_gain_sites_compensated_and_repeat_rejected(self):
        new,_=patch(self.engine())
        for at in (0x2c,0x32,0x147,0x215):self.assertEqual(new[at+4],35)
        with self.assertRaises(ValueError):patch(new)

    def test_negative_only_active_gains(self):
        new,_=patch(self.engine());bad=wrong_gain(new)
        self.assertEqual([i for i,(a,b) in enumerate(zip(new,bad)) if a!=b],[0x14b,0x219])
        with self.assertRaises(ValueError):wrong_gain(bad)

    def test_level_gate_rejects_quiet_control_and_uncentered_signal(self):
        before=dict(steady_ac_rms=[1000,1000],steady_mean=[-1200,-1200])
        good=dict(steady_ac_rms=[1003.6,1003.6],steady_mean=[10,10])
        self.assertTrue(levels(before,good)['ac_preserved'])
        self.assertTrue(levels(before,good)['dc_reduced'])
        self.assertFalse(levels(before,dict(good,steady_ac_rms=[889,889]))['ac_preserved'])
        self.assertFalse(levels(before,dict(good,steady_mean=[-1200,-1200]))['dc_reduced'])

    def test_dsp_exact_clock_and_register_allowlist(self):
        before=[dict(register=7,value=31,tick=100),dict(register=0x12,value=44,tick=110)]
        after=[dict(before[0],value=35),dict(before[1])]
        self.assertEqual(dsp_equal(before,after)['gain_writes'],1)
        for index,key in ((0,'tick'),(1,'value'),(0,'register')):
            bad=[dict(x) for x in after];bad[index][key]+=1
            with self.assertRaises(ValueError):dsp_equal(before,bad)
