import unittest
from tools.review_camera_hardware_episode import saved_configuration


class CameraHardwareReviewTests(unittest.TestCase):
    def test_both_actual_boot_and_reload_receipts(self):
        h='a'*64
        self.assertEqual(saved_configuration(dict(config_before=h,config_after=h)),h)
        self.assertEqual(saved_configuration(dict(saved_config_sha256=h)),h)

    def test_missing_invalid_and_conflicting_identity(self):
        for receipt in ({},{'config_before':'invalid'},
            {'config_before':'a'*64,'config_after':'b'*64},
            {'saved_config_sha256':'a'*64,'config_before':'b'*64}):
            with self.assertRaises(ValueError):saved_configuration(receipt)
