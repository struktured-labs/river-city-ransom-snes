import unittest
from tools.audit_camera_log_controls import differences


class CameraLogControlTests(unittest.TestCase):
    def test_missing_frame_not_neutral(self):
        row=dict(frame=1,phase='x',video_sha256='a',game_ram_hex='00',audio={})
        self.assertTrue(differences([row],[row])['timeline_exact'])
        self.assertFalse(differences([row],[])['frames_equal'])

    def test_first_difference_not_filtered(self):
        row=dict(frame=17,phase='x',video_sha256='a',game_ram_hex='00',audio={})
        result=differences([row],[dict(row,video_sha256='b')])
        self.assertFalse(result['timeline_exact'])
        self.assertEqual(result['first_difference']['video_sha256'],17)
