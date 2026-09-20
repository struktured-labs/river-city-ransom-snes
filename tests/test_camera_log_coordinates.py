import unittest
from tools.audit_camera_log_coordinates import compare


class CameraLogCoordinatesTests(unittest.TestCase):
    def rows(self, frame=1, enabled=True):
        return [dict(frame=str(frame), line=str(line), h_offset='0', v_offset='0',
                     mode='0', main_screen='1' if enabled else '0', forced_blank='0')
                for line in range(32,192)]

    def test_extra_disabled_row_retained_without_cascade(self):
        a = self.rows(2)
        b = [self.rows(1,False)[0]]+a
        r = compare(a,b,{2})
        self.assertFalse(r['exact'])
        self.assertTrue(r['eligible_camera_match'])
        self.assertEqual(len(r['differences']),1)
        self.assertFalse(r['differences'][0]['bg1_enabled_in_either'])

    def test_missing_or_duplicate_active_line_rejected(self):
        a = self.rows()
        for b in (a[1:], [a[0]]+a):
            r = compare(a,b,{1})
            self.assertFalse(r['eligible_camera_match'])
            self.assertEqual(r['missing_eligible_coverage'][1],[1])

    def test_single_pixel_scroll_mutant_rejected(self):
        a = self.rows()
        b = [dict(r) for r in a]
        b[40]['h_offset']='1'
        r = compare(a,b,{1})
        self.assertFalse(r['eligible_camera_match'])
        self.assertEqual(len(r['differences']),1)
        self.assertEqual(r['differences'][0]['line'],72)

    def test_missing_whole_frame_and_empty_stream_rejected(self):
        self.assertFalse(compare(self.rows(),[],{1})['eligible_camera_match'])
        self.assertFalse(compare([],[],set())['exact'])
