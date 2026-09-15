import unittest
from tools.analyze_audio_bus import analyze


class AudioBusTests(unittest.TestCase):
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
