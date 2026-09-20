import unittest
import numpy as np

from tools.review_restart_volume import first_volume_failures,measure


class RestartVolumeReviewTests(unittest.TestCase):
    def test_late_or_one_sided_volume_is_rejected(self):
        event=dict(packet=1,voice=0,target_volumes=[120,120],samples=[dict(left=120,right=120)]*7)
        self.assertEqual(first_volume_failures([event]),[])
        event['samples'][6]=dict(left=120,right=0)
        self.assertEqual(len(first_volume_failures([event])),1)

    def test_native_waveform_spike_and_silence(self):
        event=dict(keyon_write=dict(tick=32*20+28),samples=[dict(tick=32*28+28)]*7)
        pcm=np.zeros((150,2),np.int16);pcm[28:]=50
        good=measure(pcm,event,[event])
        self.assertEqual(good['pre_note_peak'],0)
        self.assertEqual(good['post_note_peak'],50)
        pcm[19]=32767
        self.assertEqual(measure(pcm,event,[event])['pre_note_nonzero_samples'],1)
        self.assertEqual(measure(np.zeros_like(pcm),event,[event])['post_note_peak'],0)

    def test_missing_context_rejected(self):
        event=dict(keyon_write=dict(tick=0),samples=[dict(tick=2)]*7)
        with self.assertRaises(ValueError):measure(np.zeros((150,2),np.int16),event,[event])


if __name__=='__main__':unittest.main()
