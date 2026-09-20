import unittest
from copy import deepcopy

from tools.review_wait_camera_log import CAMERA_FIELDS, compare


class WaitCameraReviewTests(unittest.TestCase):
    def row(self):
        return dict(frame=1, phase='street', video_sha256='same', game_ram_hex='00',
                    audio={}, input_requested=[], input_delivered=[],
                    native={k: 0 for k in CAMERA_FIELDS})

    def test_camera_change_not_hidden_by_equal_picture(self):
        a = self.row()
        b = deepcopy(a)
        b['native']['scroll_x'] = 1
        result = compare([a], [b])
        self.assertFalse(result['camera_fields_exact'])
        self.assertEqual(result['camera_field_differences']['scroll_x'], [1])

    def test_equal_camera_cannot_hide_picture_or_audio_change(self):
        a = self.row()
        b = dict(a, video_sha256='different', audio={'peak': 1})
        result = compare([a], [b])
        self.assertTrue(result['camera_fields_exact'])
        self.assertFalse(result['timeline_exact'])
        self.assertEqual(result['video_differences'], [1])

    def test_short_capture_not_camera_neutral(self):
        result = compare([self.row()], [])
        self.assertFalse(result['camera_fields_exact'])
        self.assertFalse(result['input_and_phase_exact'])
