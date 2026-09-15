"""Adversarial controls for the SPC signal oracle, independent of game assets."""
import unittest
import numpy as np
from tools.check_audio import measure


class AudioSignalControls(unittest.TestCase):
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

    def test_noise_during_mute_and_clipping_fail(self):
        self.assertFalse(measure(self.tone(), 48000, None)['passed'])
        self.assertFalse(measure(np.full((48000, 2), 1000), 48000, None)['passed'])
        self.assertFalse(measure(self.tone(amplitude=40000).clip(-32768, 32767), 48000, 440)['passed'])

    def test_missing_or_mono_capture_is_not_accepted(self):
        for pcm in (np.zeros((10, 2)), np.zeros((48000, 1))):
            with self.assertRaises(ValueError):
                measure(pcm, 48000, 440)
