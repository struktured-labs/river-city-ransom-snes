import unittest

from tools.capture_mister_cursor_audio import episode
from tools.mister_pad_sequence import validate


class CursorAudioCaptureTests(unittest.TestCase):
    def test_only_eight_menu_directions_never_unpauses(self):
        events=episode();self.assertAlmostEqual(validate(events),19)
        self.assertEqual([e['keys'] for e in events if e['keys']],[['right']]*4+[['left']]*4)
        self.assertEqual(events[-1],dict(keys=[],seconds=5))

    def test_every_tap_has_a_release(self):
        events=episode()
        for i,event in enumerate(events):
            if event['keys']:
                self.assertEqual(events[i+1],dict(keys=[],seconds=1.35))
