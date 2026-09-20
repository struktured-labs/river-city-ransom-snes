import unittest
import numpy as np

from tools.build_retained_return_review import pause_pair


class RawPauseTests(unittest.TestCase):
    def setUp(self):
        self.active = np.tile(np.array([[10,-10],[-10,10]],np.int32),(50,1))
        self.paused = np.zeros((100,2),np.int32)

    def test_native_integer_and_float_pairs(self):
        for dtype in (np.int32,np.float32):
            result = pause_pair(self.active.astype(dtype),self.paused.astype(dtype))
            self.assertEqual(result['paused_nonzero_samples'],0)
            self.assertEqual(result['active_channel_ac_rms'],[10,10])

    def test_dead_dc_and_single_dead_channel(self):
        for active in (self.paused,np.ones_like(self.active),self.active * [1,0]):
            with self.assertRaisesRegex(ValueError,'Dead gameplay'):
                pause_pair(active,self.paused)

    def test_one_sample_click(self):
        self.paused[50,1] = 1
        with self.assertRaisesRegex(ValueError,'non-silent pause'):
            pause_pair(self.active,self.paused)

    def test_empty_wrong_shape_and_nonfinite(self):
        for active in (self.active[:0],self.active[:,0],self.active[:,:1],
                       self.active.astype(float)*np.nan):
            with self.assertRaises(ValueError):
                pause_pair(active,self.paused)
