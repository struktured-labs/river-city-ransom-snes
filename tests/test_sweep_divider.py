import unittest
from tools.check_sweep_divider import legacy_state


class SweepDividerCharacterizationTests(unittest.TestCase):
    def test_disabled_preserves_unread_pending_counter(self):
        self.assertEqual(legacy_state(0,0x14,5,3,1),(172,5,3,64))

    def test_zero_shift_preserves_unread_pending_counter(self):
        self.assertEqual(legacy_state(1,0x90,5,3,1),(172,5,3,128))

    def test_timer_reload_discards_pending_but_not_software_count(self):
        self.assertEqual(legacy_state(0,0x94,5,3,1),(200,5,0,0))
        self.assertEqual(legacy_state(0,0x94,5,3,0),(182,0,0,0))

    def test_all_eight_dividers(self):
        for voice in (0,1):
            for p in range(8):
                threshold=3*(p+1);control=0x84|(p<<4)
                self.assertEqual(legacy_state(voice,control,threshold-1,0,0),
                                 (172,threshold-1,0,0))
                self.assertEqual(legacy_state(voice,control,threshold-1,1,0),(182,0,0,0))
