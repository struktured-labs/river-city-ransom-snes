import unittest

import numpy as np

from tools.audit_replay_short_silence import gate, gate_segments, gap_gate_context, command_segments


class ReplayShortSilenceTests(unittest.TestCase):
    def test_packet_quiet_boundary(self):
        quiet = bytes(23)
        active = bytearray(23)
        active[0] = 0x3f
        active[2] = 50
        active[21] = 1
        data = b'\1'+quiet+b'\0\1'+active
        spans = command_segments(data, {1:dict(tick=28),2:dict(tick=348)},0,30)
        self.assertEqual([(s['first'],s['last'],s['zero_output_commanded']) for s in spans],
                         [(0,10,True),(10,30,False)])

    def test_echo_prevents_false_quiet(self):
        regs = [0]*128
        regs[0x2c] = 1
        self.assertFalse(gate(regs)['echo_muted'])

    def test_all_eight_voices_count(self):
        regs = [0]*128
        regs[0x70] = 255
        self.assertEqual(gate(regs)['voice_mask'], 128)

    def test_exact_write_boundary_and_unchanged_coalescing(self):
        writes = [dict(tick=1, register=0x0c, value=127),
                  dict(tick=28, register=0, value=127),
                  dict(tick=40, register=2, value=3),
                  dict(tick=28+32*10, register=0, value=0)]
        segments = gate_segments(writes, 0, 30)
        self.assertEqual([(s['first'],s['last'],s['zero_output_commanded']) for s in segments],
                         [(0,10,False),(10,30,True)])

    def test_injected_short_gap_not_excused_by_nearby_mute(self):
        segments = [dict(first=0,last=10,zero_output_commanded=True),
                    dict(first=10,last=30,zero_output_commanded=False)]
        pcm = np.ones((30,2), dtype='<i2')
        pcm[8:20] = 0
        gaps, censored = gap_gate_context(pcm,1000,segments)
        self.assertFalse(censored)
        self.assertEqual(gaps[0]['active_command_samples'],10)
        self.assertEqual(gaps[0]['zero_output_command_samples'],2)

    def test_boundary_gaps_retained_as_censored(self):
        pcm = np.zeros((30,2), dtype='<i2')
        gaps, censored = gap_gate_context(pcm,1000,[dict(first=5,last=25,zero_output_commanded=True)])
        self.assertFalse(gaps)
        self.assertEqual(censored[0]['first'],0)
