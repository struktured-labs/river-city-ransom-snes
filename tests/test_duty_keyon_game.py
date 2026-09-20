import unittest

import numpy as np

from tools.audit_duty_keyon_game import adjacent_metrics, parse_keyons, synth_rows


class DutyKeyonGameAuditTests(unittest.TestCase):
    def test_keyon_parser_separates_startup_and_gameplay(self):
        rows = [['K', '0', '0', '0bcb'], ['K', '0', '15', '0456'],
                ['P', '1', '1', '15', '191', '63', '3008'],
                ['K', '1', '1', '04c5']]
        packets, events = parse_keyons(rows)
        self.assertEqual(packets, 1)
        self.assertEqual(events, [{'packet': 1, 'voice_bits': 1, 'pc': 0x04C5}])

    def test_out_of_order_keyon_is_rejected(self):
        rows = [['K', '0', '0', '0bcb'], ['K', '0', '15', '0456'],
                ['K', '1', '1', '04c5']]
        with self.assertRaises(ValueError):
            parse_keyons(rows)

    def test_adjacent_metric_detects_single_impulse(self):
        quiet = np.zeros((8, 2), dtype=np.int16)
        impulse = quiet.copy(); impulse[4] = 1000
        self.assertEqual(adjacent_metrics(quiet)['max'], 0)
        self.assertEqual(adjacent_metrics(impulse)['max'], 1000)

    def test_synth_parser_rejects_unknown_marker(self):
        self.assertEqual(synth_rows([['P', '1', '20', '3008']]), [('P', 1, 20, 0x3008)])
        with self.assertRaises(ValueError):
            synth_rows([['X', '1', '20', '3008']])


if __name__ == '__main__':
    unittest.main()
