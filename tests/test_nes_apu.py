import unittest
from tools.analyze_nes_apu import analyze, first_difference


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
