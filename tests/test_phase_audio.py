import unittest
from tools.audit_phase_audio import phase_rows


class PhaseAudioTests(unittest.TestCase):
    def test_phase_is_exact_contiguous_sequence(self):
        rows=[dict(frame=i,phase='entry' if 2<=i<=4 else 'other') for i in range(1,6)]
        self.assertEqual(phase_rows(rows,'entry'),rows[1:4])

    def test_missing_or_repeated_phase_rejected(self):
        with self.assertRaises(ValueError):phase_rows([],'entry')
        rows=[dict(frame=1,phase='entry'),dict(frame=2,phase='other'),dict(frame=3,phase='entry')]
        with self.assertRaises(ValueError):phase_rows(rows,'entry')
