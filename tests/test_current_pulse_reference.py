import unittest

import numpy as np

from tools.build_current_pulse_reference import stimulus
from tools.audit_current_pulse_reference import measure
from tools.audit_retrigger_transient import evaluate


class CurrentPulseReferenceTests(unittest.TestCase):
    def test_all_duties_both_periods_and_frame_correspondence(self):
        nes,packets,cases=stimulus()
        self.assertEqual((len(nes),len(packets),len(cases)),(1084,1084,8))
        self.assertEqual({(c['period'],c['duty']) for c in cases},
                         {(p,d) for p in (0xfd,0x6c6) for d in range(4)})
        for c in cases:
            for frame in range(c['first_frame'],c['last_frame']+1):
                p=packets[frame-1]
                self.assertEqual(p[4:8],bytes((c['control'],8,c['period']&255,c['period']>>8)))
                self.assertEqual(p[21],2)
                high=any(reg==7 for reg,_ in nes[frame-1])
                self.assertEqual(bool(p[20]&32),high)
                self.assertEqual(bool(p[22]&2),high)
        self.assertTrue(all(p==bytes(23) for p in packets[1024:]))
        self.assertEqual(nes[1024],[(0x15,0)])

    def test_controls_only_remove_periodic_resets(self):
        nes,a,cases=stimulus();control,b,_=stimulus(True)
        resets={f for c in cases for f in c['reset_frames']}
        self.assertEqual(len(resets),24)
        for i,(x,y) in enumerate(zip(a,b),1):
            if i in resets:
                self.assertEqual([j for j,(v,w) in enumerate(zip(x,y)) if v!=w],[20,22])
                self.assertEqual(nes[i-1],[(7,control[i-1][0][1])])
                self.assertEqual(control[i-1][0][0],3)
                self.assertEqual(y[21],2)  # redirected other pulse remains disabled
            else:
                self.assertEqual(x,y);self.assertEqual(nes[i-1],control[i-1])

    def test_fixed_window_metrics_retain_dc_and_use_native_samples(self):
        rate=48000;count=800
        rows=[dict(start_sample=i*count,end_sample=(i+1)*count) for i in range(128)]
        case=dict(first_frame=1,last_frame=128,reset_frames=[33,65,97],period=0xfd)
        t=np.arange(128*count)/rate
        signal=np.round(3000*np.sin(2*np.pi*(1789773/(16*254))*t)-1000).astype(np.int16)
        pcm=np.column_stack((signal,signal))
        r=measure(pcm,rate,rows,case)
        self.assertAlmostEqual(r['steady_mean'][0],-1000,delta=15)
        self.assertTrue(r['fundamental']['passed'])
        self.assertEqual(r['events'][0]['first'],32*count)
        bad=pcm.copy();bad[32*count+10:32*count+12]=[[-32768,-32768],[32767,32767]]
        gates,_=evaluate(r,measure(bad,rate,rows,case))
        self.assertFalse(all(g['passed'] for g in gates))
        with self.assertRaises(ValueError):measure(np.zeros_like(pcm),rate,rows,case)

    def test_existing_relative_step_failure_not_redefined_as_pass(self):
        reference=dict(max_step_to_signal_peak=4784/5538,max_step_to_full_scale=4784/32768,
                       longest_near_zero_ms=0,clipped_fraction=0)
        candidate=dict(max_step_to_signal_peak=1,max_step_to_full_scale=2309/32768,
                       longest_near_zero_ms=5*1000/32040,clipped_fraction=0)
        gates,_=evaluate(reference,candidate)
        self.assertEqual([g['gate'] for g in gates if not g['passed']],['step_relative_to_signal_peak'])
