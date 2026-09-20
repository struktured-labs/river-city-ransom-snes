import unittest
from tools.check_sweep_driver import clock_step,muted,audit_deadlines
from tools.build_native import build
from pathlib import Path


class SweepDriverTests(unittest.TestCase):
    def test_residual_is_not_discarded(self):
        self.assertEqual(clock_step(8542,0,0,1),(511,1,1))
        self.assertEqual(clock_step(8544,1,0,1),(511,0,1))

    def test_five_step_long_interval(self):
        self.assertEqual(clock_step(12813,1,128,1),(511,0,1))

    def test_disabled_sweep_still_mutes_overflow(self):
        self.assertTrue(muted(1024,0))
        self.assertFalse(muted(1024,8))
        self.assertTrue(muted(7,8))
        self.assertFalse(muted(8,8))

    def test_missing_last_events_cannot_pass(self):
        self.assertFalse(audit_deadlines([8543],0,40000,0)['passed'])
        self.assertTrue(audit_deadlines([8543,17088,25631,34176],0,40000,0)['passed'])

    def test_final_late_window_is_censored(self):
        self.assertTrue(audit_deadlines([8543,17088,25631],0,35000,0)['passed'])
        self.assertFalse(audit_deadlines([8543,17088,25631,34176,35000],0,35000,0)['passed'])

    def test_build_rejects_incompatible_engines_before_writing(self):
        for options in ({},dict(experimental_paired_audio=True),
                dict(experimental_paired_audio=True,experimental_reset_audio=True,experimental_pulse_sweep=True)):
            with self.assertRaisesRegex(ValueError,'Live sweep driver requires'):
                build(Path('missing.nes'),[],Path('must-not-be-created'),experimental_sweep_driver=True,**options)
