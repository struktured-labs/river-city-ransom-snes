import unittest

from tools.audit_pause_audio_timing import compare, late_onset


class PauseAudioTimingTests(unittest.TestCase):
    def test_onset_not_loudness_and_late_control(self):
        peaks=[2000]*32+[100]*25+[1500]*5+[0]*58
        self.assertEqual(late_onset(peaks)['frame_offset'],57)
        self.assertTrue(compare(peaks,[x*2 for x in peaks])['passed'])
        self.assertFalse(compare(peaks,[0,0]+peaks[:-2])['passed'])

    def test_dead_flat_and_truncated_rejected(self):
        for peaks in ([0]*120,[2000]*120,[2000]*119):
            with self.assertRaises(ValueError):
                late_onset(peaks)
