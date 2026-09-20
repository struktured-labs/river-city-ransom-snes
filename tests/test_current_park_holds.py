from copy import deepcopy
import unittest

from tools.audit_current_park_holds import classify
from tools.audit_display_cadence import measure


class CurrentParkHoldTests(unittest.TestCase):
    def fixture(self):
        phases = {'park': measure([dict(frame=f, camera=0 if f < 5 else 2 if f < 19 else 4 if f < 21 else 6)
                                  for f in range(1, 23)])}
        loops = [dict(start=dict(frame=f-1), commit=dict(frame=f, camera=2 if f < 18 else 4 if f < 20 else 6),
                      finish=dict(frame=f+1), nmi_advances=2) for f in range(4, 21, 2)]
        rows = [dict(frame=f, phase='park', game_ram_hex=bytes(2048).hex(),
                     input_requested=[7], input_delivered=[7]) for f in range(1, 24)]
        return phases, loops, rows

    def test_repeated_commands_require_full_display_and_loop_evidence(self):
        phases, loops, rows = self.fixture()
        event, = classify(phases, loops, rows, 'snes')
        self.assertEqual(event['hold']['frames'], 14)
        self.assertEqual(event['classification'], 'repeated_command_regular_updates')
        self.assertEqual(event['repeated_camera_commits'], 6)
        self.assertTrue(event['complete_snes_two_tick_loops'])

    def test_missing_or_slow_update_is_unresolved(self):
        for kind in ('missing', 'slow'):
            phases, loops, rows = self.fixture()
            if kind == 'missing':
                loops.pop(2)
            else:
                loops[2]['nmi_advances'] = 3
            event, = classify(phases, loops, rows, 'snes')
            self.assertEqual(event['classification'], 'unresolved')

    def test_late_endpoint_is_not_repeated_command_explanation(self):
        phases, loops, rows = self.fixture()
        series = phases['park']['series']
        series[18]['camera'] = 2
        phases['park'] = measure(series)
        event, = classify(phases, loops, rows, 'snes')
        self.assertEqual(event['classification'], 'unresolved')

    def test_nes_does_not_imply_measured_finish(self):
        phases, loops, rows = self.fixture()
        for loop in loops:
            del loop['finish'], loop['nmi_advances']
        event, = classify(phases, loops, rows, 'nes')
        self.assertIsNone(event['complete_snes_two_tick_loops'])
        self.assertEqual(event['classification'], 'repeated_command_regular_updates')

    def test_no_repeat_does_not_explain_a_hold(self):
        phases, loops, rows = self.fixture()
        for i, loop in enumerate(loops):
            loop['commit']['camera'] = i+1
        event, = classify(phases, loops, rows, 'snes')
        self.assertEqual(event['classification'], 'unresolved')

    def test_bad_timeline_derivation_and_order_rejected(self):
        for kind in ('timeline', 'derivation', 'order'):
            phases, loops, rows = self.fixture()
            if kind == 'timeline':
                rows.pop(3)
            elif kind == 'derivation':
                phases['park']['intervals'][0]['frames'] = 13
            else:
                loops[2]['commit']['frame'] = loops[1]['commit']['frame']
            with self.assertRaises(ValueError):
                classify(phases, loops, rows, 'snes')
