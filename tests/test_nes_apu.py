import unittest
from tools.analyze_nes_apu import analyze, first_difference, matched_frame_timing


class NesApuTests(unittest.TestCase):
    def test_exact_phase_attribution_and_repeated_writes(self):
        events, counts = analyze([[1, 3, 0x4002, 0], [1, 4, 0x4002, 0], [2, 9, 0x4015, 15]], ['menu', 'start'])
        self.assertEqual(counts, {'menu': 2, 'start': 1})
        self.assertEqual(len(events), 3)
        self.assertEqual(events[-1]['phase'], 'start')

    def test_bad_frame_cycle_and_empty_rejected(self):
        for rows in ([], [[3, 0, 0x4000, 0]], [[1, 5, 0x4000, 0], [1, 4, 0x4000, 0]]):
            with self.assertRaises(ValueError):
                analyze(rows, ['menu'])

    def test_sequence_comparison_does_not_realign(self):
        result = first_difference([(1, 2), (1, 3)], [(1, 2), (1, 2), (1, 3)])
        self.assertEqual(result['common_prefix_writes'], 1)

    def test_timing_retains_drift_and_unmatched_tail(self):
        events, _ = analyze([[1, 1, 0x4000, 1], [3, 2, 0x4000, 2],
                             [5, 3, 0x4000, 3]], ['menu']*5)
        native = [['W', f, 1, 1, 1, 0, v, 'c12090']
                  for f, v in [(11, 1), (14, 2), (15, 9), (16, 3)]]
        result = matched_frame_timing(events, native, 'menu')
        self.assertEqual(result['relative_frame_drift_histogram'], {0: 1, 1: 1})
        self.assertEqual(result['unmatched_reference_tail'], 1)
        self.assertEqual(result['unmatched_candidate_tail'], 2)
        self.assertEqual(result['reference_span_frames'], 2)
        self.assertEqual(result['candidate_span_frames'], 3)
        with self.assertRaises(ValueError):
            matched_frame_timing(events, native, 'absent')

    def test_menu_audio_has_no_input(self):
        from tools.benchmark_capture import scenario_for
        phases = scenario_for('menu-audio')
        self.assertEqual(phases[-1], {'name': 'menu_audio', 'frames': 1800})
        self.assertTrue(all(not p.get('buttons') for p in phases))
