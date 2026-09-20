import unittest
from tools.analyze_audio_bus import analyze


class AudioBusTests(unittest.TestCase):
    def test_ordered_enable_oracle_preserves_upper_bits_and_reset_flags(self):
        rows = self.packet() + [self.event('W', 21, 0)]
        rows += [self.event('W', i, 0) for i in (3, 7, 11, 15)]
        rows += [self.event('W', 21, 31)]
        packet = self.packet(flags=207)
        packet[21][6] = '16'
        self.assertEqual(analyze(rows+packet, length_gate=True)['mismatches'], [])
        self.assertTrue(analyze(rows+packet)['mismatches'])
        packet[21][6] = '31'
        self.assertTrue(analyze(rows+packet, length_gate=True)['mismatches'])

    def test_valid_reload_restores_only_its_channel(self):
        rows = self.packet() + [self.event('W', 21, 15), self.event('W', 7, 0)]
        packet = self.packet(flags=130)
        packet[21][6] = '2'
        self.assertEqual(analyze(rows+packet, length_gate=True)['mismatches'], [])
        rows += [self.event('W', 21, 13)]
        packet[21][6] = '0'
        self.assertEqual(analyze(rows+packet, length_gate=True)['mismatches'], [])

    def event(self, kind, index, value, frame=1):
        return [kind, str(frame), '240', '100', '1', str(index), str(value), 'c12090']

    def packet(self, period=0, flags=0):
        data = [0]*23
        data[2], data[22] = period, flags
        return [self.event('P', i, value) for i, value in enumerate(data)]

    def test_last_value_and_accumulated_flags(self):
        rows = self.packet() + [self.event('W', 2, 0), self.event('W', 2, 9)] + self.packet(9, 64)
        result = analyze(rows)
        self.assertEqual(result['mismatches'], [])
        self.assertEqual(result['changing_register_groups_between_packets'][0]['values'], [0, 9])

    def test_stale_data_and_missing_event_flag_are_detected(self):
        for period, flags in ((0, 64), (9, 0)):
            rows = self.packet() + [self.event('W', 2, 9)] + self.packet(period, flags)
            self.assertTrue(analyze(rows)['mismatches'])

    def test_missing_byte_and_interleaving_rejected(self):
        for rows in ([], self.packet()[:-1], self.packet()[1:],
                     self.packet()[:2] + [self.event('W', 2, 9)]):
            with self.assertRaises(ValueError):
                analyze(rows)

    def test_disabled_reload_reenabled_before_publication(self):
        rows = self.packet() + [self.event('W', 21, 0), self.event('W', 3, 8),
                                self.event('W', 21, 1)]
        packet = self.packet(flags=65)
        packet[3][6] = '8'
        packet[21][6] = '1'
        result = analyze(rows + packet)
        self.assertEqual(result['mismatches'], [])
        hazards = result['disabled_reload_then_enabled_in_packet']
        self.assertEqual(len(hazards), 1)
        self.assertEqual(hazards[0]['channel'], 0)
        self.assertEqual(hazards[0]['final_flags'], 65)

    def test_enabled_reload_is_not_disabled_ordering_hazard(self):
        for enabled in (None, 1):
            rows = self.packet()
            if enabled is not None:
                rows.append(self.event('W', 21, enabled))
            rows.append(self.event('W', 3, 8))
            self.assertEqual(analyze(rows + self.packet())['disabled_reload_then_enabled_in_packet'], [])
