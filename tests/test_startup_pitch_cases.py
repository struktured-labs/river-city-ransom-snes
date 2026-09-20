import unittest

from tools.build_startup_pitch_cases import stimulus


class CasesTests(unittest.TestCase):
    def test_both_voice_masks_and_muted_restart_without_disable(self):
        packets, cases = stimulus()
        self.assertEqual(len(cases), 36)
        self.assertEqual(len(packets), 1788)
        self.assertEqual({c['mask'] for c in cases}, {1, 2, 3})
        for case in cases:
            before = packets[case['first_frame']-1]
            changed = packets[case['changed_frame']-1]
            muted = packets[case['muted_restart_frame']-1]
            resume = packets[case['resume_frame']-1]
            self.assertEqual((changed[22], muted[22], muted[21], resume[22]),
                             (case['mask'], case['mask'], 3, 0))
            for v in (0, 1):
                a, b = before[4*v+2:4*v+4], changed[4*v+2:4*v+4]
                self.assertEqual(a != b, bool(case['mask'] & (1 << v)))
                self.assertEqual((muted[4*v] & 15, resume[4*v] & 15), (0, 15))


if __name__ == '__main__':
    unittest.main()
