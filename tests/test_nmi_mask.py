import unittest

from tools.analyze_nmi_mask import analyze


def event(frame, line, enabled, pc='c72354', cycle=100):
    return [str(frame), str(line), str(cycle), pc, str(128 if enabled else 0),
            '192', '0', '0', '136']


class NmiMaskTests(unittest.TestCase):
    def test_short_bank_switch_does_not_cross_edge(self):
        self.assertEqual(analyze([event(10, 200, False), event(10, 205, True)])
                         ['masked_vblank_edges'], 0)

    def test_line_zero_has_not_advanced_frame_counter(self):
        report = analyze([event(10, 238, False), event(10, 0, True)])
        self.assertEqual(report['masked_vblank_edges'], 1)

    def test_nmi_entry_after_edge_is_not_itself_missed(self):
        self.assertEqual(analyze([event(10, 240, False), event(11, 132, True)])
                         ['masked_vblank_edges'], 0)

    def test_multiple_frames_and_unfinished_span(self):
        report = analyze([event(10, 238, False), event(12, 1, True),
                          event(12, 10, False)])
        self.assertEqual(report['masked_vblank_edges'], 2)
        self.assertTrue(report['incomplete_final_span'])

    def test_reject_reordered_trace(self):
        with self.assertRaises(ValueError):
            analyze([event(11, 10, False), event(10, 20, True)])
