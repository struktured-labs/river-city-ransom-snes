import unittest
from tools.analyze_duty_changes import classify


class DutyChangeTests(unittest.TestCase):
    def packet(self, control, reset=0):
        data = bytearray(23)
        data[0], data[21], data[22] = control, 1, reset
        return dict(frame=1, bytes=data.hex())

    def test_duty_only_candidate(self):
        result = classify([self.packet(0x3F), self.packet(0xBF)])
        self.assertEqual(result['enabled_constant_volume_without_note_reset'], 1)

    def test_note_reset_is_distinguished(self):
        result = classify([self.packet(0x3F), self.packet(0xBF, 1)])
        self.assertEqual(result['duty_changes'], 1)
        self.assertEqual(result['enabled_constant_volume_without_note_reset'], 0)

    def test_envelope_zero_is_not_classified_as_constant_silence(self):
        result = classify([self.packet(0x00), self.packet(0x80)])
        self.assertFalse(result['events'][0]['constant_volume'])
        self.assertEqual(result['enabled_constant_volume_changes'], 0)

    def test_reject_incomplete_packet(self):
        with self.assertRaises(ValueError):
            classify([dict(frame=0, bytes='00')])
