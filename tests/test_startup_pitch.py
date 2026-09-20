import unittest

from tools.build_startup_pitch_trial import helpers, patch, ORIGIN, VALID


class StartupPitchTests(unittest.TestCase):
    def test_helpers_do_not_overlap_storage(self):
        code, labels = helpers()
        self.assertLessEqual(ORIGIN+len(code), VALID)
        self.assertEqual(set(labels), {'stage0', 'stage1', 'ordinary0', 'ordinary1',
                                      'flush', 'skip0', 'skip1', 'finish'})
        self.assertEqual(code.count(bytes.fromhex('cd101dd0fd')), 1)

    def test_wrong_engine_or_delay_fails(self):
        with self.assertRaisesRegex(ValueError, 'exact current'):
            patch(bytes(12415), {})
        for delay in (0, 256, -1):
            with self.assertRaises(ValueError):
                helpers(delay)


if __name__ == '__main__':
    unittest.main()
