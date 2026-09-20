import unittest
from tools.check_camera_wait_boundary import before_vblank, pointer_after


class CameraWaitBoundaryTests(unittest.TestCase):
    def test_line_zero_counter_roll_is_not_vblank(self):
        self.assertTrue(before_vblank(0,814,4,5596))
        self.assertTrue(before_vblank(193,800,198,6000))

    def test_late_or_wrapped_interval_rejected(self):
        self.assertFalse(before_vblank(239,800,243,5596))
        self.assertFalse(before_vblank(193,800,2,100000))
        self.assertFalse(before_vblank(239,1300,239,40))

    def test_all_sram_bank_rollovers(self):
        for bank in range(0x20,0x2F):
            self.assertEqual(pointer_after(bank,0x7FE0),(bank+1,0x6000))
        self.assertEqual(pointer_after(0x2F,0x7FE0),(0x20,0x6020))
        self.assertEqual(pointer_after(0x20,0x6020),(0x20,0x6040))
