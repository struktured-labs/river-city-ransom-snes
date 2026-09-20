import unittest
import numpy as np
from tools.audit_dsp_latency import dac_tick,next_dac_sample,callback_frame,validate_trace,raw_identity


class DspLatencyTests(unittest.TestCase):
    def fixture(self):
        return ([['P','1','31','1','0'],['D','1','60','2','28','76','3'],
                 ['R','1','63','2','0'],['B','100','0','100']],
                [dict(frame=1,audio_start_sample=0,audio=dict(samples=100))])

    def test_exact_dac_tick_boundary(self):
        for sample in (0,1,50,3507953):
            tick=dac_tick(sample)
            self.assertEqual(next_dac_sample(tick),sample)
            self.assertEqual(next_dac_sample(tick+1),sample+1)
            self.assertEqual(next_dac_sample(tick-1),sample)

    def test_callback_assignment_has_no_fitted_offset(self):
        self.assertEqual(callback_frame([0,100],[100,200],99),1)
        self.assertEqual(callback_frame([0,100],[100,200],100),2)
        self.assertIsNone(callback_frame([0,100],[100,200],200))
        self.assertIsNone(callback_frame([0,100],[100,200],-1))

    def test_packet_pending_clocks_and_register_phase(self):
        trace,rows=self.fixture()
        packets,writes,callbacks=validate_trace(trace,rows,100)
        self.assertEqual(packets[0]['received_tick'],32)
        self.assertEqual(writes[0]['sample'],2)
        self.assertEqual(callbacks[0]['end'],100)

    def test_clock_phase_missing_packet_and_wrong_register_fail(self):
        for index,column,value in ((0,1,'2'),(0,3,'0'),(1,2,'59'),(1,4,'32'),
                                   (1,5,'128'),(2,1,'0')):
            trace,rows=self.fixture();trace[index][column]=value
            with self.assertRaises(ValueError):validate_trace(trace,rows,100)

    def test_callback_backlog_gap_and_truncation_fail(self):
        for column,value in ((1,'101'),(2,'1'),(3,'99')):
            trace,rows=self.fixture();trace[-1][column]=value
            with self.assertRaises(ValueError):validate_trace(trace,rows,100)
        trace,rows=self.fixture()
        with self.assertRaises(ValueError):validate_trace(trace[:-1],rows,100)
        with self.assertRaises(ValueError):validate_trace(trace,rows,99)

    def test_raw_pcm_must_be_identical_without_gain_or_delay(self):
        raw=np.arange(200,dtype='<i2').reshape(-1,2)
        raw_identity(raw,raw.copy())
        for wrong in (raw[:-1],raw*2,np.roll(raw,1,axis=0)):
            with self.assertRaises(ValueError):raw_identity(raw,wrong)
