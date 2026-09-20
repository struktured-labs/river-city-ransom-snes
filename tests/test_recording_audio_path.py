import unittest
import numpy as np
from tools.audit_recording_audio_path import metrics, nearby


class RecordingAudioPathTests(unittest.TestCase):
    def test_silence_and_dc_are_not_ac_audio(self):
        for level in (0, 42):
            result = metrics(np.full((48000, 2), level, dtype=np.int16), 48000)
            self.assertEqual(result['ac_rms_by_channel'], [0, 0])

    def test_signal_and_clipping_remain_explicit(self):
        pcm = np.zeros((48000, 2), dtype=np.int16)
        pcm[::2] = 32767
        result = metrics(pcm, 48000)
        self.assertGreater(result['ac_rms_by_channel'][0], 1)
        self.assertEqual(result['clipped_samples'], 48000)

    def test_short_wrong_geometry_rejected(self):
        for samples, rate in ((np.zeros((10, 2)), 48000), (np.zeros((48000, 1)), 48000),
                              (np.zeros((48000, 2)), 32040)):
            with self.assertRaises(ValueError):metrics(samples, rate)

    def test_stale_settings_and_other_live_inputs_do_not_qualify(self):
        p = dict(recording_duration_ms=12698, recording_active=True, scene='river city ransom',
                 blackmagic=dict(mute=False, volume=.42), desktop_muted=True, microphone_muted=True)
        self.assertTrue(nearby(p, 0, 12))
        self.assertFalse(nearby(dict(p, microphone_muted=False), 0, 12))
        with self.assertRaises(ValueError):nearby(p, 0, 9)
