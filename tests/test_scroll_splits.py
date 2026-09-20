import unittest
from tools.audit_scroll_splits import scan, eligible


class ScrollSplitTests(unittest.TestCase):
    def rows(self):
        return [dict(frame=5,line=y,mode=0,main_screen=1,forced_blank=0,h_offset=42)
                for y in range(32,192)]

    def test_requires_all_lines_and_rejects_duplicates(self):
        rows=self.rows()
        for bad in (rows[:-1],rows+rows[:1]):
            with self.assertRaises(ValueError):scan(bad,[5])

    def test_one_wrong_line_is_retained(self):
        rows=self.rows();rows[40]['h_offset']=44
        result=scan(rows,[5])
        self.assertEqual(set(result[5].values()),{42,44})

    def test_unsupported_selected_frame_is_not_skipped(self):
        rows=self.rows();rows[2]['forced_blank']=1
        with self.assertRaisesRegex(ValueError,'Unsupported'):scan(rows,[5])

    def test_eligibility_uses_game_state_not_pixel_match(self):
        r=dict(native=dict(task=192,transition_state=0,ppu_mask=24))
        self.assertTrue(eligible(r))
        r['native']['transition_state']=2
        self.assertFalse(eligible(r))
