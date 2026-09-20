import unittest

import numpy as np

from tools.audit_gameplay_transients import (
    correlate_events, evaluate, measure, validate_timeline,
)


class GameplayTransientAuditTests(unittest.TestCase):
    def timeline(self):
        return [
            {'frame': 1, 'phase': 'idle', 'audio_start_sample': 0, 'audio': {'samples': 4}},
            {'frame': 2, 'phase': 'move', 'audio_start_sample': 4, 'audio': {'samples': 4}},
        ]

    def test_timeline_is_contiguous_and_positive(self):
        result = validate_timeline(self.timeline(), 8, 2)
        self.assertEqual(result['minimum_callback_samples'], 4)
        for mutation in ('zero', 'gap', 'count', 'total'):
            rows = [dict(row, audio=dict(row['audio'])) for row in self.timeline()]
            samples, frames = 8, 2
            if mutation == 'zero':
                rows[0]['audio']['samples'] = 0
            elif mutation == 'gap':
                rows[1]['audio_start_sample'] = 5
            elif mutation == 'count':
                frames = 3
            else:
                samples = 9
            with self.assertRaises(ValueError, msg=mutation):
                validate_timeline(rows, samples, frames)

    def test_event_packet_mapping_is_exact(self):
        rows = [
            ['P', '1', '0', '1', '0', '0', '3008'],
            ['P', '2', '1', '1', '0', '0', '3008'],
            ['P', '3', '0', '1', '64', '0', '3008'],
        ]
        bus = [dict(frame=1), dict(frame=2), dict(frame=2)]
        events, packets, total = correlate_events(rows, bus, self.timeline())
        self.assertEqual((packets, total), (2, 3))
        self.assertEqual(events, [dict(frame=2, packets=[2, 3], reset_bits=1,
                                       duty_bits=1, keyon_bits=1)])

    def test_measurement_and_reference_bound_reject_spike(self):
        pcm = np.zeros((8, 2), dtype=np.int16)
        pcm[:, 0] = [0, 10, 20, 30, 40, 50, 60, 70]
        events = [dict(frame=2, packets=[2], reset_bits=1, duty_bits=0, keyon_bits=1)]
        result = measure(pcm, self.timeline(), events)
        self.assertTrue(all(g['passed'] for g in evaluate(result, .1)))
        pcm[5] = -32768
        pcm[6] = 32767
        result = measure(pcm, self.timeline(), events)
        self.assertFalse(all(g['passed'] for g in evaluate(result, .1)))


if __name__ == '__main__':
    unittest.main()
