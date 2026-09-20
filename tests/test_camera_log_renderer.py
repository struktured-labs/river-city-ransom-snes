import unittest
from tools.audit_camera_log_renderer import compare_lines


class CameraLogRendererTests(unittest.TestCase):
    def test_changed_scanline_rejected(self):
        a = [dict(frame=1, line=32, h_offset=12), dict(frame=1, line=33, h_offset=12)]
        b = [dict(a[0]), dict(a[1], h_offset=11)]
        result = compare_lines(iter(a), iter(b))
        self.assertFalse(result['exact'])
        self.assertEqual(result['mismatches'][0]['row'], 2)
        self.assertTrue(compare_lines(iter(a), iter(a))['exact'])

    def test_missing_duplicate_or_empty_rows_rejected(self):
        a = [dict(frame=1, line=32)]
        for b in ([], a+a):
            self.assertFalse(compare_lines(iter(a), iter(b))['exact'])
        self.assertFalse(compare_lines(iter([]), iter([]))['exact'])
