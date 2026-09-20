import unittest
from xml.etree import ElementTree

import numpy as np

from tools.audit_dsp_latency import dac_tick
from tools.audit_hardware_replay_gaps import envelope, overlap, register_context, waveform_svg
from tools.audit_raw_monitor_audio import locate, score


class HardwareReplayGapTests(unittest.TestCase):
    def test_envelope_recovers_known_shift_and_held_out_match(self):
        rng = np.random.default_rng(20260918)
        # Independent 2ms amplitudes at 48kHz, with an exact 74ms delay.
        amplitude = rng.uniform(.01, .9, 1500)
        predicted = np.repeat(amplitude, 96)
        physical = np.r_[np.zeros(37 * 96), predicted, np.zeros(96)]
        ref = envelope(np.column_stack([predicted] * 2), 48000, 1)
        actual = envelope(np.column_stack([physical] * 2), 48000, 1)
        found = locate(actual, ref, 100, 500)
        self.assertEqual(found['offset_samples'], 37)
        self.assertGreater(found['training_correlation'], .9999)
        self.assertGreater(score(actual, ref, 37, 800, 1200), .9999)
        # A held-out dropout remains a failure without changing the offset.
        actual[837:1037] = -7
        self.assertLess(score(actual, ref, 37, 800, 1200), .5)

    def test_bad_pcm_rejected_and_silence_not_alignment_pass(self):
        for pcm, rate, scale in ((np.zeros(10), 48000, 1),
                                 (np.zeros((10, 2)), 0, 1),
                                 (np.zeros((10, 2)), 48000, 0),
                                 (np.full((1000, 2), np.nan), 48000, 1),
                                 (np.zeros((1, 2)), 48000, 1)):
            with self.subTest(rate=rate, scale=scale), self.assertRaises(ValueError):
                envelope(pcm, rate, scale)
        silent = envelope(np.zeros((48000, 2)), 48000, 1)
        with self.assertRaises(ValueError):
            locate(silent, silent, 10, 100)

    def test_overlap_has_no_nearest_gap_false_positive(self):
        self.assertEqual(overlap((1, 2), (3, 4)), 0)
        self.assertEqual(overlap((1, 2), (2, 3)), 0)
        self.assertEqual(overlap((1, 2), (1.5, 3)), .5)
        self.assertEqual(overlap((1, 2), (0, 3)), 1)

    def test_gain_release_not_confused_with_zero_volume(self):
        writes = [dict(tick=dac_tick(0), register=0x20, value=31),
                  dict(tick=dac_tick(1), register=0x27, value=0x9f),
                  dict(tick=dac_tick(3), register=0x27, value=0xdf)]
        context = register_context(writes, 2)
        self.assertEqual(context['registers']['20'], 31)
        self.assertEqual(context['registers']['27'], 0x9f)
        self.assertEqual(context['triangle_gain_write'], writes[1])
        self.assertEqual(register_context(writes, 3)['registers']['27'], 0xdf)

    def test_svg_escapes_labels_and_keeps_full_scale(self):
        pcm = np.array([[-32768, 0], [0, 0], [16384, 0]], dtype=np.int16)
        svg = waveform_svg([('A < B & C', pcm, 20, 32768, .05)])
        root = ElementTree.fromstring(svg)
        line = root.find('.//{http://www.w3.org/2000/svg}polyline')
        self.assertEqual(line.attrib['points'], '300.00,200.00 520.00,125.00 740.00,87.50')
        self.assertIn('A &lt; B &amp; C', svg)


if __name__ == '__main__':
    unittest.main()
