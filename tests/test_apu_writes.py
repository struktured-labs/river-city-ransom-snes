import unittest
from tools.analyze_apu_writes import analyze


class ApuWriteTests(unittest.TestCase):
    def row(self, frame=1, value=0):
        return [str(frame), '20', '100', '1', '16386', str(value), 'c12090']

    def test_repeated_zero_and_changed_writes_retained(self):
        report = analyze([self.row(), self.row(), self.row(value=9)])
        self.assertEqual(report['writes'], 3)
        self.assertEqual(report['repeated_groups'][0]['values'], [0, 0, 9])
        self.assertEqual(report['changing_register_frame_groups'], 1)

    def test_empty_bad_value_and_time_reversal_rejected(self):
        for rows in ([], [self.row(value=256)], [self.row(frame=2), self.row(frame=1)]):
            with self.assertRaises(ValueError):
                analyze(rows)
