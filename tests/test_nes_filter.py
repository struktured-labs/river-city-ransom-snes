import unittest
import numpy as np
from tools.audit_nes_filter import step,reconstruct,window


class NesFilterTests(unittest.TestCase):
    def fixture(self):
        a1=a2=0;raw=[]
        for value in [1000]*10+[0]*30:
            y,a1,a2=step(value,a1,a2,128,32,147456)
            raw.append((value,y))
        raw=np.array(raw,dtype='<i4');pcm=np.repeat(raw[:,1:2],2,axis=1).astype('<i2')
        return raw,[[0,40,48000,0,0,128,32,147456,0,0]],pcm

    def test_exact_integer_reconstruction(self):
        raw,blocks,pcm=self.fixture()
        self.assertEqual(reconstruct(raw,blocks,pcm,48000),40)

    def test_constant_input_filter_tail_is_not_continuing_wave(self):
        raw,_,_=self.fixture();metrics=window(raw,10,40)
        self.assertTrue(metrics['constant_input'])
        self.assertGreater(metrics['output_ac_rms'],0)

    def test_one_sample_excitation_not_hidden_by_threshold(self):
        raw,_,_=self.fixture();raw[20,0]=1
        self.assertFalse(window(raw,10,40)['constant_input'])

    def test_mutated_input_fails_even_with_original_output(self):
        raw,blocks,pcm=self.fixture();raw[20,0]+=20
        with self.assertRaisesRegex(ValueError,'recurrence'):reconstruct(raw,blocks,pcm,48000)

    def test_shift_gain_and_single_channel_failure_rejected(self):
        raw,blocks,pcm=self.fixture()
        for bad in (np.roll(pcm,1,axis=0),pcm*2,np.column_stack((pcm[:,0],pcm[:,0]*0))):
            with self.assertRaises(ValueError):reconstruct(raw,blocks,bad,48000)

    def test_wrong_state_coefficient_lowpass_and_coverage_fail(self):
        for column,value in ((0,1),(1,39),(2,44100),(3,1),(4,1),(5,129),(8,1)):
            raw,blocks,pcm=self.fixture();blocks[0][column]=value
            with self.assertRaises(ValueError):reconstruct(raw,blocks,pcm,48000)

    def test_out_of_bounds_window_fails(self):
        raw,_,_=self.fixture()
        for a,b in ((-1,4),(3,3),(2,41)):
            with self.assertRaises(ValueError):window(raw,a,b)
