import unittest
import numpy as np
from tools.audit_cursor_audio import cues, checks


class CursorAudioAuditTests(unittest.TestCase):
    def pcm(self):
        pcm = np.zeros((3000,2))
        for first in (300,1800):
            pcm[first:first+70] = .1
        return pcm

    def test_isolated_cues(self):
        events = cues(self.pcm(),1000)
        self.assertEqual([e['first'] for e in events],[300,1800])
        self.assertTrue(checks(events,[2,3.5])['passed'])

    def test_silence_is_not_a_pass(self):
        self.assertFalse(checks(cues(np.zeros((3000,2)),1000),[2,3.5])['passed'])

    def test_internal_cut_detected(self):
        pcm = self.pcm(); pcm[320:330] = 0
        result = checks(cues(pcm,1000),[2,3.5])
        self.assertFalse(result['gates']['no_internal_2ms_exact_zero'])

    def test_short_pulse_zeros_are_not_dropouts(self):
        pcm = self.pcm(); pcm[330] = 0
        self.assertTrue(checks(cues(pcm,1000),[2,3.5])['passed'])

    def test_delayed_event_detected(self):
        self.assertFalse(checks(cues(self.pcm(),1000),[2,3.6])['passed'])

    def test_extra_event_detected(self):
        pcm = self.pcm(); pcm[1000:1070] = .1
        self.assertFalse(checks(cues(pcm,1000),[2,3.5])['passed'])

    def test_small_tail_does_not_extend_strong_duration(self):
        pcm = self.pcm(); pcm[370:500] = .001
        events = cues(pcm,1000)
        self.assertEqual(events[0]['duration_ms'],200)
        self.assertEqual(events[0]['strong_duration_ms'],70)

    def test_invalid_audio(self):
        for pcm in (np.zeros(3000),np.full((3000,2),np.nan)):
            with self.assertRaises(ValueError):
                cues(pcm,1000)
