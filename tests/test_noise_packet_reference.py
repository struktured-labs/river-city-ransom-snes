import unittest

import numpy as np

from tools.build_noise_packet_reference import dead_store, stimulus
from tools.review_noise_packet_reference import frame_window, measure, validate_timeline


class NoisePacketReferenceTests(unittest.TestCase):
    def packet(self):
        p = bytearray(23)
        p[12], p[14], p[21] = 0x35, 0x47, 15
        return p

    def test_exact_snapshot_values_and_one_initial_load(self):
        p = self.packet()
        rows = stimulus((b'\1'+p)*3)
        self.assertEqual(rows[0], [(0x17,0x40),(0x15,8),(12,0x35),(14,0x47),(15,0)])
        self.assertEqual(rows[1:], [[(12,0x35),(14,0x47)]]*2)

    def test_unsupported_state_does_not_get_silently_approximated(self):
        for reg,value in ((12,0x15),(12,0x25),(14,0x87),(15,8),(21,7),(21,31),(17,1)):
            p = self.packet(); p[reg] = value
            with self.assertRaises(ValueError): stimulus(b'\1'+p)
        for data in (b'', b'\1', b'\0'+self.packet(), b'\2'+self.packet()):
            with self.assertRaises(ValueError): stimulus(data)

    def test_physical_store_control_preserves_instrumentation(self):
        rom = bytes.fromhex('009d00409d2002ff')
        self.assertEqual(dead_store(rom), bytes.fromhex('009d00509d2002ff'))
        for bad in (b'',rom+rom):
            with self.assertRaises(ValueError):dead_store(bad)

    def test_whole_frame_selection_preserves_boundaries_and_rejects_gaps(self):
        rows=[dict(source_frame=i+1,start_sample=10+i*10,end_sample=20+i*10) for i in range(3)]
        validate_timeline(rows,3,40)
        self.assertEqual(frame_window(rows,20,30),(2,2))
        self.assertEqual(frame_window(rows,19,31),(1,3))
        with self.assertRaises(ValueError):frame_window(rows,9,31)
        with self.assertRaises(ValueError):validate_timeline(rows[1:],3,40)
        rows[1]['start_sample']+=1
        with self.assertRaises(ValueError):validate_timeline(rows,3,40)

    def test_native_step_keeps_preceding_sample_and_silence(self):
        x=np.zeros((100,2),dtype=np.int16);x[20:30]=1000
        result=measure(x,48000,20,30)
        self.assertEqual(result['max_step'],1000)
        self.assertEqual(result['step_to_peak'],1)
        self.assertIsNone(measure(x,48000,40,50)['step_to_peak'])
        with self.assertRaises(ValueError):measure(x.astype(float),48000,20,30)
