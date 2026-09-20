import unittest

import numpy as np

from tools.analyze_game_silence import analyze, packet_context, voice_state


def packet(voice=0, control=0x31):
    data = bytearray(23)
    data[voice*4] = control
    data[voice*4+2] = 100
    data[21] = 1 << voice
    return data


class GameSilenceTests(unittest.TestCase):
    def test_all_constant_held_voices_and_explicit_mutes(self):
        for voice in range(4):
            p = packet(voice, 0x81 if voice == 2 else 0x31)
            self.assertEqual(voice_state(p.hex()), (1 << voice, False))
            p[voice*4] = 0x80 if voice == 2 else 0x30
            self.assertEqual(voice_state(p.hex()), (0, True))
            p[21] = 0
            self.assertEqual(voice_state(p.hex()), (0, True))

    def test_no_silence_claim_for_envelopes_sweep_or_short_period(self):
        p = packet(control=0x21)
        self.assertEqual(voice_state(p.hex()), (0, False))
        p = packet(); p[1] = 0x80
        self.assertEqual(voice_state(p.hex()), (0, False))
        p = packet(); p[2] = 7
        self.assertEqual(voice_state(p.hex()), (0, False))
        p = packet(control=0x30); p[21] |= 16
        self.assertEqual(voice_state(p.hex()), (0, False))

    def test_retained_state_and_same_voice_required(self):
        packets = [dict(frame=1, bytes=packet().hex()),
                   dict(frame=8, bytes=packet(1).hex())]
        self.assertEqual(packet_context(packets, 5, 5)['held_voice_mask'], 1)
        self.assertEqual(packet_context(packets, 6, 7)['classification'], 'boundary_or_unresolved')
        self.assertEqual(packet_context(packets, 1, 1)['classification'], 'outside_packet_coverage')
        self.assertEqual(packet_context(packets, 8, 8)['classification'], 'outside_packet_coverage')

    def test_inserted_silent_frame_rejected_not_normal_rest(self):
        rows = [dict(frame=i+1, audio_start_sample=i*800,
                     audio=dict(samples=800), phase='game') for i in range(10)]
        packets = [dict(frame=i+1, bytes=packet().hex()) for i in range(10)]
        pcm = np.full((8000, 2), 100, dtype='<i2')
        self.assertTrue(analyze(pcm, 48000, rows, packets)['held_voice_silence_passed'])
        pcm[4000:4800] = 0
        result = analyze(pcm, 48000, rows, packets)
        self.assertFalse(result['held_voice_silence_passed'])
        self.assertEqual((result['gaps'][0]['first_frame'], result['gaps'][0]['last_frame']), (6, 6))
        for p in packets:
            p['bytes'] = packet(control=0x30).hex()
        result = analyze(pcm, 48000, rows, packets)
        self.assertFalse(result['held_voice_silence_passed'])  # no positive active coverage
        self.assertEqual(result['held_voice_frames'], [])
        self.assertEqual(result['classifications']['commanded_silence'], 1)

    def test_mute_boundary_is_context_not_causal_pass(self):
        packets = [dict(frame=i, bytes=packet(control=0x30 if i in (5,6) else 0x31).hex())
                   for i in range(1, 10)]
        result = packet_context(packets, 5, 6)
        self.assertEqual(result['classification'], 'boundary_or_unresolved')
        self.assertTrue(result['mute_command_in_or_before_gap'])

    def test_invalid_geometry_packets_and_callback_holes_rejected(self):
        with self.assertRaises(ValueError):
            voice_state('00')
        with self.assertRaises(ValueError):
            packet_context([], 1, 1)
        with self.assertRaises(ValueError):
            packet_context([dict(frame=2), dict(frame=1)], 1, 1)
        with self.assertRaises(ValueError):
            analyze(np.zeros((1, 2), '<i2'), 48000,
                [dict(frame=1, audio_start_sample=1, audio=dict(samples=1), phase='game')], [])
