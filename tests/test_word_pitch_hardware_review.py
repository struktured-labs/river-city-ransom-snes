import unittest

from tools.build_word_pitch_hardware_review import describe_candidate, describe_controls


class WordPitchHardwareReviewTests(unittest.TestCase):
    def test_failed_audio_controls_never_inherit_passing_claim(self):
        for silent in (True, False):
            for dropout in (True, False):
                page = describe_controls('Silent-monitor and injected-dropout controls pass.',
                    dict(muted_monitor_negative_rejected=silent,
                         synthetic_100ms_aac_only_cut=dict(detected=dropout)))
                self.assertIn('negative: '+('PASS' if silent else 'FAIL'), page)
                self.assertIn('control: '+('PASS' if dropout else 'FAIL'), page)
                self.assertNotIn('controls pass.', page)

    def test_replaces_old_candidate_claim_once_and_keeps_scope(self):
        old = ('Timing-balanced pitch publication is now running on Rival. Emulator evidence is separate: '
               '<a href="../balanced-pitch-review-1509/">pitch A/B and retained strict callback failure</a>. ')
        page = describe_candidate('BEGIN '+old+'END')
        self.assertTrue(page.startswith('BEGIN ') and page.endswith('END'))
        self.assertIn('five-clock', page)
        self.assertIn('not identical-state hardware A/B', page)
        self.assertNotIn('retained strict callback failure', page)
        for invalid in ('', old+old, old.replace('1509', '0000')):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                describe_candidate(invalid)


if __name__ == '__main__':
    unittest.main()
