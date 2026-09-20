import copy

import unittest

from tools.build_pulse_onset_review import paired_events


def example():
    events = [dict(packet=1, voice=0, target_pitch=418, stale_nonzero_voice_samples=[]),
              dict(packet=2, voice=1, target_pitch=3054, stale_nonzero_voice_samples=[{}])]
    return dict(baseline=dict(events=events), candidate=dict(events=copy.deepcopy(events)))


class PulseOnsetReviewTests(unittest.TestCase):
    def test_worst_first_pairing(self):
        report = example()
        report['candidate']['events'].reverse()
        pairs = paired_events(report)
        self.assertEqual([a['packet'] for a, _ in pairs], [2, 1])
        self.assertTrue(all(a['packet'] == b['packet'] and a['voice'] == b['voice'] for a, b in pairs))

    def test_reject_different_onsets(self):
        for damage in ('missing', 'duplicate', 'pitch'):
            with self.subTest(damage=damage):
                report = example()
                events = report['candidate']['events']
                if damage == 'missing':
                    events.pop()
                elif damage == 'duplicate':
                    events.append(copy.deepcopy(events[0]))
                else:
                    events[0]['target_pitch'] += 1
                with self.assertRaises(ValueError):
                    paired_events(report)
