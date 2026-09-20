import unittest

from tools.review_noise_source_first import ordering
from tools.build_noise_mute_transition_cases import stimulus


def writes(registers):
    return [dict(packet=p,register=r,value=v,tick=i+1)
            for i,(p,r,v) in enumerate(registers)]


class NoisePublication(unittest.TestCase):
    def test_nonzero_requires_source_and_pitch_before_volume(self):
        cases=[dict(first_frame=1,last_frame=1,period=6,volume=4)]
        pitches=[0]*16;pitches[6]=0x1234
        prefix=[(0,0x34,5),(1,0x3d,0),(1,0x32,0x34),(1,0x33,0x12)]
        volume=[(1,0x30,8),(1,0x31,8)]
        self.assertTrue(ordering(writes(prefix+volume),cases,pitches)['passed'])
        self.assertFalse(ordering(writes(prefix[:2]+volume+prefix[2:]),cases,pitches)['passed'])
        with self.assertRaises(ValueError):ordering(writes(prefix),cases,pitches)

    def test_zero_command_mutes_both_before_switch(self):
        cases=[dict(first_frame=1,last_frame=1,period=2,volume=0)]
        initial=[(0,0x30,30),(0,0x31,30)]
        quiet=[(1,0x30,0),(1,0x31,0)];source=[(1,0x3d,8)]
        self.assertTrue(ordering(writes(initial+quiet+source),cases,[0]*16)['passed'])
        self.assertFalse(ordering(writes(initial+quiet[:1]+source+quiet[1:]),cases,[0]*16)['passed'])

    def test_zero_cases_remain_enabled(self):
        packets,cases=stimulus()
        self.assertEqual(len(packets),268)
        zeros=[c for c in cases if c['volume']==0]
        self.assertEqual(len(zeros),2)
        for c in zeros:
            for p in packets[c['first_frame']-1:c['last_frame']]:
                self.assertEqual((p[12],p[14],p[21]),(0x30,c['period'],8))


if __name__=='__main__':unittest.main()
