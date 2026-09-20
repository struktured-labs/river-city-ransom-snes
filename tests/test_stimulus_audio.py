import unittest
import numpy as np
from tools.audit_stimulus_audio import select, metrics, frame_metrics


class StimulusAudioTests(unittest.TestCase):
    def test_no_frame_rematching(self):
        with self.assertRaisesRegex(ValueError, 'Missing/reordered'):
            select([dict(frame=1), dict(frame=3)], 'frame', 1, 3)

    def test_metrics_preserve_raw_gain_and_steps(self):
        result = metrics(np.array([[0, 0], [1000, -1000], [-2000, 2000]], dtype=np.int16))
        self.assertEqual(result['peak'], 2000)
        self.assertEqual(result['max_step'], 3000)
        self.assertEqual(result['step_to_peak'], 1.5)

    def test_silence_is_not_a_fidelity_pass(self):
        result = metrics(np.zeros((10, 2), dtype=np.int16))
        self.assertIsNone(result['step_to_peak'])
        self.assertNotIn('passed', result)

    def test_frame_silence_uses_both_channels_and_no_threshold(self):
        pcm = np.array([[0,0], [0,0], [0,1], [0,0]], dtype=np.int16)
        rows = [dict(source_frame=1, start_sample=0, end_sample=2),
                dict(source_frame=2, start_sample=2, end_sample=4)]
        result = frame_metrics(pcm, rows, True)
        self.assertEqual([r['peak'] for r in result], [0,1])
        self.assertEqual([r['source_frame'] for r in result], [1,2])
        rows[1]['start_sample'] = 1
        with self.assertRaisesRegex(ValueError, 'Noncontiguous'):
            frame_metrics(pcm, rows, True)

    def test_snes_frame_bounds_use_callback_sample_count(self):
        pcm = np.zeros((8,2), dtype=np.int16)
        rows = [dict(frame=24, audio_start_sample=2, audio=dict(samples=3)),
                dict(frame=25, audio_start_sample=5, audio=dict(samples=3))]
        self.assertEqual([r['samples'] for r in frame_metrics(pcm, rows, False)], [3,3])
        rows[1]['audio']['samples'] = 4
        with self.assertRaisesRegex(ValueError, 'invalid'):
            frame_metrics(pcm, rows, False)
