import unittest
import numpy as np
from tools.audit_silence_reference import frame_energy, diagnose


class SilenceReferenceTests(unittest.TestCase):
    def setUp(self):
        self.pcm=np.zeros((1000,2),dtype='<i2')
        self.rows=[dict(frame=i+1,audio_start_sample=i*100,audio=dict(samples=100)) for i in range(10)]
        self.nesrows=[dict(source_frame=i+1,start_sample=i*100,end_sample=(i+1)*100) for i in range(10)]
        self.tone=np.tile(np.array([[100,-100],[-100,100]],dtype='<i2'),(500,1))

    def result(self, source=None, reference=None):
        source=self.pcm if source is None else source
        reference=self.tone if reference is None else reference
        return diagnose(source,1000,frame_energy(source,self.rows,nes=False),
                        frame_energy(reference,self.nesrows,nes=True))

    def test_sustained_sound_inside_silence_flagged(self):
        r=self.result()
        self.assertEqual(r['sustained_mismatch_count'],1)
        self.assertEqual(r['gaps'][0]['longest_active_reference_run'],8)
        self.assertEqual([x['source_frame'] for x in r['gaps'][0]['reference_frames']],list(range(2,10)))

    def test_dc_silent_or_dead_channel_not_sustained_control(self):
        one=self.tone.copy();one[:,1]=0
        for pcm in (self.pcm,np.full_like(self.pcm,100),one):
            self.assertEqual(self.result(reference=pcm)['sustained_mismatch_count'],0)

    def test_short_and_boundary_only_sound_does_not_flag(self):
        tone=np.zeros_like(self.tone);tone[:200]=self.tone[:200];tone[800:]=self.tone[800:]
        r=self.result(reference=tone)
        self.assertEqual(r['sustained_mismatch_count'],0)
        self.assertEqual(r['gaps'][0]['longest_active_reference_run'],1)

    def test_one_callback_gap_retained_without_interior(self):
        pcm=self.tone.copy();pcm[400:500]=0
        r=self.result(source=pcm)
        self.assertEqual(r['gaps'][0]['classification'],'no_guarded_interior')
        self.assertEqual(r['gaps'][0]['milliseconds'],100)

    def test_injected_five_callback_dropout_detected_in_active_audio(self):
        self.assertEqual(self.result(source=self.tone)['sustained_mismatch_count'],0)
        mutated=self.tone.copy();mutated[200:700]=0
        r=self.result(source=mutated)
        self.assertEqual(r['sustained_mismatch_count'],1)
        self.assertEqual(r['gaps'][0]['longest_active_reference_run'],3)
        self.assertEqual(r['gaps'][0]['first_frame'],3)

    def test_noncontiguous_or_reordered_callbacks_fail(self):
        for key,value in (('source_frame',9),('start_sample',99),('end_sample',1001)):
            rows=[dict(r) for r in self.nesrows];rows[1][key]=value
            with self.assertRaises(ValueError):frame_energy(self.tone,rows,nes=True)
        with self.assertRaises(ValueError):frame_energy(self.tone[:-1],self.nesrows,nes=True)

    def test_signal_and_thresholds_are_not_fitted(self):
        quiet=(self.tone//10).astype('<i2')
        self.assertEqual(self.result(reference=quiet)['sustained_mismatch_count'],0)
        before=self.tone.copy();self.result();np.testing.assert_array_equal(before,self.tone)
        frames=frame_energy(self.tone,self.rows,nes=False)
        for rate,threshold in ((0,32),(1000,0),(1000,float('nan'))):
            with self.assertRaises(ValueError):diagnose(self.pcm,rate,frames,frames,ac_threshold=threshold)
