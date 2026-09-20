import unittest
import numpy as np

from tools.review_nes_volume_sensitivity import compare_pcm


class NESVolumeMeasurement(unittest.TestCase):
    def test_exact_difference_and_step_not_pop_verdict(self):
        a=np.array([[0,0],[100,100],[100,100],[0,0]],dtype=np.int16)
        b=np.array([[0,0],[100,200],[0,100],[0,0]],dtype=np.int16)
        r=compare_pcm(a,b)
        self.assertEqual(r['changed_sample_frames'],2)
        self.assertEqual(r['max_absolute_difference'],100)
        self.assertEqual((r['baseline_max_step'],r['suppressed_max_step']),(100,200))
        self.assertEqual(r['suppressed_clipped_samples'],0)
        self.assertEqual(compare_pcm(a,a)['changed_sample_frames'],0)

    def test_format_length_and_signed_overflow(self):
        a=np.array([[-32768,0],[32767,0]],dtype=np.int16)
        b=np.zeros_like(a)
        r=compare_pcm(a,b)
        self.assertEqual(r['baseline_max_step'],65535)
        self.assertEqual(r['max_absolute_difference'],32768)
        for wrong in (b[:1],b.astype(float),b[:,0]):
            with self.assertRaises(ValueError):compare_pcm(a,wrong)


if __name__=='__main__':unittest.main()
