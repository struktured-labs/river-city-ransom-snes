"""Adversarial controls for the SPC signal oracle, independent of game assets."""
import unittest
import numpy as np
from tools.check_audio import measure, measure_length


class AudioSignalControls(unittest.TestCase):
    def test_length_requires_audible_onset_and_silent_tail(self):
        onset = self.tone()[:1920]
        silence = np.zeros((48000, 2))
        self.assertTrue(measure_length(onset, silence, 48000)['passed'])
        self.assertFalse(measure_length(onset, self.tone(), 48000)['passed'])
        self.assertFalse(measure_length(onset*0, silence, 48000)['passed'])
        dead_channel = onset.copy(); dead_channel[:, 1] = 0
        self.assertFalse(measure_length(dead_channel, silence, 48000)['passed'])
        with self.assertRaises(ValueError):
            measure_length(onset[:10], silence, 48000)

    def tone(self, frequency=440, amplitude=2000):
        signal = amplitude*np.sin(2*np.pi*frequency*np.arange(48000)/48000)
        return np.column_stack((signal, signal))

    def test_tone_and_mute(self):
        self.assertTrue(measure(self.tone(), 48000, 440)['passed'])
        self.assertTrue(measure(np.zeros((48000, 2)), 48000, None)['passed'])

    def test_wrong_pitch_dead_channel_and_dropouts_fail(self):
        wrong = self.tone(660)
        one_channel = self.tone(); one_channel[:, 1] = 0
        sputter = self.tone(); sputter[20000:24800] = 0
        for pcm in (wrong, one_channel, sputter, np.full((48000, 2), 1000)):
            self.assertFalse(measure(pcm, 48000, 440)['passed'])

    def test_submillisecond_gap_is_not_hidden_by_10ms_activity(self):
        tone = self.tone()
        tone[24000:24048] = 0
        result = measure(tone, 48000, 440)
        self.assertGreaterEqual(min(result['active_10ms_fraction']), .98)
        self.assertGreater(max(result['longest_near_zero_ms']), .5)
        self.assertFalse(result['passed'])

    def test_noise_during_mute_and_clipping_fail(self):
        self.assertFalse(measure(self.tone(), 48000, None)['passed'])
        self.assertFalse(measure(np.full((48000, 2), 1000), 48000, None)['passed'])
        self.assertFalse(measure(self.tone(amplitude=40000).clip(-32768, 32767), 48000, 440)['passed'])

    def test_missing_or_mono_capture_is_not_accepted(self):
        for pcm in (np.zeros((10, 2)), np.zeros((48000, 1))):
            with self.assertRaises(ValueError):
                measure(pcm, 48000, 440)
