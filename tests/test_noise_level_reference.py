import unittest

import numpy as np

from tools.build_noise_level_reference import stimulus
from tools.review_noise_level_reference import measure


class NoiseLevelReferenceTests(unittest.TestCase):
    def test_rate_volume_grid_and_real_enable_controls(self):
        writes,packets,cases=stimulus()
        self.assertEqual((len(writes),len(packets),len(cases)),(2220,2220,30))
        self.assertEqual({(c['period'],c['volume']) for c in cases if c['channel']=='noise'},
            {(p,v) for p in range(2,16) for v in (4,15)})
        for c in cases:
            self.assertEqual(c['last_frame']-c['first_frame'],63)
            active=packets[c['first_frame']-1:c['last_frame']]
            for p in active:
                self.assertEqual(p[21],8 if c['channel']=='noise' else 1)
                if c['channel']=='noise':self.assertEqual((p[12],p[14]),(0x30|c['volume'],c['period']))
            self.assertEqual(writes[c['last_frame']],[(0x15,0)])
            self.assertTrue(all(p==bytes(23) for p in packets[c['last_frame']:c['last_frame']+8]))
        self.assertTrue(all(p==bytes(23) for p in packets[-60:]))

    def test_pulse_reset_only_at_case_entry_and_noise_no_retrigger(self):
        writes,packets,cases=stimulus()
        for c in cases:
            first=c['first_frame']-1
            self.assertTrue(any(reg==3 if c['channel']=='pulse' else reg==15 for reg,_ in writes[first]))
            self.assertTrue(all(not row for row in writes[first+1:c['last_frame']]))
            self.assertEqual(packets[first][20],0x1c if c['channel']=='pulse' else 0)
            self.assertTrue(all(p[20]==0 and p[22]==0 for p in packets[first+1:c['last_frame']]))

    def test_measurement_preserves_level_and_rejects_silent_channel(self):
        signal=np.rint(3000*np.sin(2*np.pi*np.arange(256)/16)).astype(np.int16)
        pcm=np.column_stack((signal,signal));original=pcm.copy()
        a=measure(pcm,48000,16,240);b=measure(pcm*2,48000,16,240)
        self.assertAlmostEqual(b['ac_rms'][0]/a['ac_rms'][0],2)
        self.assertEqual(a['peak'],3000);self.assertEqual(b['peak'],6000)
        self.assertTrue(np.array_equal(pcm,original))
        pcm[:,1]=0
        with self.assertRaises(ValueError):measure(pcm,48000,16,240)
