import unittest

from tools.build_combat_outlier_review import context, excerpt_bounds, outliers


class CombatOutlierReviewTests(unittest.TestCase):
    def test_two_ticks_does_not_hide_long_physical_frame_span(self):
        rows = [dict(phase='combat_counterattack') for _ in range(100)]
        loops = [dict(start=dict(frame=a), finish=dict(frame=b), nmi_advances=2)
                 for a, b in ((1, 3), (3, 28), (28, 30))]
        selected = outliers(loops, rows)
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]['start_spacing'], 25)
        self.assertEqual(selected[0]['loop']['start']['frame'], 3)

    def test_inter_loop_gap_is_not_lost_or_paired_across_phases(self):
        rows = [dict(phase='attack') for _ in range(10)] + [dict(phase='pause') for _ in range(10)]
        loops = [dict(start=dict(frame=a), finish=dict(frame=b), nmi_advances=2)
                 for a, b in ((1, 3), (6, 8), (11, 13))]
        selected = outliers(loops, rows)
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]['start_spacing'], 5)

    def rows(self):
        ram = bytearray(2048); ram[0x100] = 192
        return [dict(frame=i+1, game_ram_hex=ram.hex(), native=dict(transition_state=0),
                     audio_start_sample=i*533, audio=dict(samples=533, ac_rms=12)) for i in range(100)]

    def test_transition_annotation_does_not_waive_failure(self):
        rows = self.rows()
        ram = bytearray.fromhex(rows[42]['game_ram_hex']); ram[0x42] = 1
        rows[42]['game_ram_hex'] = ram.hex()
        rows[42]['native']['transition_state'] = 2
        event = context(dict(start=dict(frame=40), finish=dict(frame=45), nmi_advances=7), rows)
        self.assertTrue(event['room_change'])
        self.assertTrue(event['native_transition_observed'])
        self.assertFalse(event['strict_gate_waived'])
        self.assertEqual(len(event['states']), 6)

    def test_clip_uses_actual_callback_boundaries_including_end(self):
        rows = self.rows()
        self.assertEqual(excerpt_bounds(rows, 1, 3), (1, 33, 0, 33*533))
        self.assertEqual(excerpt_bounds(rows, 95, 100), (65, 100, 64*533, 100*533))

    def test_invalid_coverage_rejected(self):
        rows = self.rows()
        for first, last in ((0, 1), (5, 4), (99, 101)):
            with self.assertRaises(ValueError):
                context(dict(start=dict(frame=first), finish=dict(frame=last), nmi_advances=3), rows)
