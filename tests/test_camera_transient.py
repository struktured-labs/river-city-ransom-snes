import unittest
from tools.audit_camera_transient import classify


class CameraTransientTests(unittest.TestCase):
    def setUp(self):
        self.first = dict(frame=10, room=2, working=252, committed=0, published=0)
        self.stable = dict(frame=100, room=2, working=252, committed=252, published=252)
        self.zero = dict.fromkeys(range(32, 192), 0)
        self.target = dict.fromkeys(range(32, 192), 252)

    def test_working_only_transient(self):
        self.assertTrue(classify(self.first, self.stable, self.zero, self.target))

    def test_rendered_glitch_is_not_excused(self):
        bad = self.zero | {80: 252}
        self.assertFalse(classify(self.first, self.stable, bad, self.target))

    def test_late_publication_is_not_excused(self):
        self.assertFalse(classify(self.first | dict(committed=252), self.stable, self.zero, self.target))

    def test_missing_line_is_rejected(self):
        self.zero.pop(191)
        with self.assertRaisesRegex(ValueError, 'Incomplete'):
            classify(self.first, self.stable, self.zero, self.target)
