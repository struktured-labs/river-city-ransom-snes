import copy
import unittest
import numpy as np
from pathlib import Path
from tools.build_native import build
from tools.audit_triangle_release import boundary, preservation


class TriangleReleaseTests(unittest.TestCase):
    def test_game_release_requires_known_transport_before_any_file_access(self):
        for flags in ({},dict(experimental_paired_audio=True),
                      dict(experimental_paired_audio=True,experimental_reset_audio=True,experimental_triple_audio=True)):
            with self.assertRaisesRegex(ValueError,'paired fast-reset'):
                build(Path('/nonexistent.nes'),[],Path('/nonexistent-out'),experimental_triangle_release=True,**flags)

    def report(self):
        return dict(passed=True, receipt=dict(audio_peak=1000),
                    phases=[dict(phase=i,ac_rms=[0,0] if i==1 else [500,500]) for i in range(4)])

    def test_preservation_rejects_gain_change_and_silent_channel(self):
        baseline=self.report()
        self.assertTrue(preservation(baseline,copy.deepcopy(baseline))['passed'])
        for value in (0,2000):
            candidate=copy.deepcopy(baseline);candidate['phases'][0]['ac_rms'][1]=value
            self.assertFalse(preservation(baseline,candidate)['passed'])

    def test_failed_tone_or_larger_peak_not_accepted(self):
        a=self.report();b=self.report();b['passed']=False
        self.assertFalse(preservation(a,b)['passed'])
        b=self.report();b['receipt']['audio_peak']=1100
        self.assertFalse(preservation(a,b)['passed'])

    def test_boundary_checks_both_channels_without_normalizing(self):
        pcm=np.zeros((100,2),np.int16);pcm[50,1]=32767
        r=boundary(pcm,1000,[dict(frame=5,start_sample=40,end_sample=60)],'frame',5)
        self.assertEqual(r['max_step'],32767)
        self.assertEqual(r['clipped_samples'],1)
        self.assertEqual(r['channel_max_steps'],[0,32767])

    def test_missing_boundary_and_coverage_fail(self):
        pcm=np.zeros((100,2),np.int16)
        for rows in ([],[dict(frame=5,start_sample=0,end_sample=60)],
                     [dict(frame=5,start_sample=40,end_sample=60)]*2):
            with self.assertRaises(ValueError):boundary(pcm,1000,rows,'frame',5)


if __name__=='__main__': unittest.main()
