import unittest
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import wave

import numpy as np

from tools.audit_recorded_transients import audit, measure, sensitivity, zero_runs
from tools.audit_hardware_pause_pair import read_pcm


class RecordedTransientTests(unittest.TestCase):
    def setUp(self):
        self.pcm = np.full((48000, 2), 100, dtype='<i2')

    def test_zero_runs_include_boundaries_and_require_both_channels(self):
        self.pcm[:3] = 0
        self.pcm[9:14] = 0
        self.pcm[20:40, 0] = 0
        self.pcm[-2:] = 0
        self.assertEqual(zero_runs(self.pcm), [(0, 3), (9, 14), (47998, 48000)])

    def test_step_polarity_channel_and_true_sample_number(self):
        self.pcm[12000, 1] = -32768
        self.pcm[12001, 1] = 32767
        result = measure(self.pcm)
        top = result['strongest_separated_events'][0]
        self.assertEqual((top['sample'], top['channel'], top['step']), (12001, 1, 65535))
        self.assertEqual((top['before'], top['after']), (-32768, 32767))
        self.assertEqual(result['clipped_samples'], 2)
        self.assertFalse(result['pop_free_verified'])

    def test_ranked_events_are_separated_not_duplicate_attack_samples(self):
        self.pcm[100:103] = 2000
        self.pcm[36000] = 1000
        result = measure(self.pcm)
        events = result['strongest_separated_events']
        self.assertEqual([e['sample'] for e in events[:2]], [100, 36000])
        for i, a in enumerate(events):
            for b in events[i+1:]:
                self.assertGreater(abs(a['sample']-b['sample']), 24000)

    def test_silence_and_click_injections_are_detected(self):
        self.assertTrue(all(sensitivity(self.pcm, 48000).values()))
        self.pcm[300:1260] = 0
        result = measure(self.pcm)
        self.assertEqual(result['longest_exact_zero_frames'], 960)
        self.assertEqual(result['exact_zero_runs_at_least_10ms'],
            [dict(first_sample=300, last_sample=1260, seconds=0.02)])

    def test_rejects_wrong_geometry_and_dtype(self):
        for pcm, rate in ((self.pcm[:, 0], 48000), (self.pcm.astype(float), 48000),
                          (self.pcm, 32040), (self.pcm[:20], 48000)):
            with self.assertRaises(ValueError):
                measure(pcm, rate)

    def test_review_clips_are_exact_slices_with_recording_offsets(self):
        self.pcm[12000:12960] = 0
        with TemporaryDirectory() as directory:
            root = Path(directory)
            with wave.open(str(root/'source.wav'), 'wb') as target:
                target.setparams((2, 2, 48000, 0, 'NONE', 'not compressed'))
                target.writeframes(self.pcm.tobytes())
            audit(root/'source.wav', 10, root/'review')
            result = json.loads((root/'review/report.json').read_text())
            for item in (result['strongest_separated_events'] +
                         result['exact_zero_runs_at_least_10ms']):
                data = read_pcm(root/'review'/item['clip'])
                np.testing.assert_array_equal(data,
                    self.pcm[item['clip_first_sample']:item['clip_last_sample']])
                at = item.get('sample', item.get('first_sample'))
                self.assertEqual(item['recording_seconds'], 10+at/48000)
                self.assertIn(item['clip'], result['clips_sha256'])


if __name__ == '__main__':
    unittest.main()
