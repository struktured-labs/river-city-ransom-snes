import unittest
from tools.audit_display_cadence import cameras,measure,rendering_enabled


class DisplayCadenceTests(unittest.TestCase):
    def test_blank_state_is_not_a_missing_camera(self):
        self.assertFalse(rendering_enabled(dict(nes_ppu=dict(mask=0)),'nes'))
        self.assertTrue(rendering_enabled(dict(nes_ppu=dict(mask=8)),'nes'))
        self.assertFalse(rendering_enabled(dict(native=dict(ppu_mask=8,transition_state=2)),'snes'))

    def test_shifted_frame_exposes_one_three_pair(self):
        def series(values):return [dict(frame=f,camera=v) for f,v in enumerate(values,1)]
        normal=measure(series([0,0,2,2,4,4,6,6]))
        mutant=measure(series([0,0,2,4,4,4,6,6]))
        self.assertEqual(normal['hold_histogram'],{2:2})
        self.assertEqual(mutant['hold_histogram'],{1:1,3:1})
        self.assertEqual(len(mutant['uniform_two_pixel_1_3_pairs']),1)

    def test_long_stops_and_wrap_are_retained(self):
        result=measure([dict(frame=f,camera=v) for f,v in enumerate([510,0,0,0,0,0,2,2],1)])
        self.assertEqual(result['hold_histogram'],{5:1})
        self.assertEqual(result['changes'][0]['delta'],2)
        self.assertEqual(result['trailing_censored_hold'],2)
        with self.assertRaises(ValueError):measure([dict(frame=1,camera=0),dict(frame=3,camera=2)])

    def test_all_lines_required_and_splits_visible(self):
        rows=[dict(frame=1,line=y,h_offset=2,v_offset=0,mode=0,main_screen=1,forced_blank=0) for y in range(32,192)]
        self.assertEqual(cameras(rows,'snes',[1]),{1:[2]})
        rows[-1]['h_offset']=4
        self.assertEqual(cameras(rows,'snes',[1]),{1:[2,4]})
        for bad in (rows[:-1],rows+[rows[0]]):
            with self.assertRaises(ValueError):cameras(bad,'snes',[1])

    def test_every_nes_group_required(self):
        rows=[dict(frame=1,line=y,group=g,older_address=g,newer_address=g+1 if g<31 else 0x400,
                   fine_x=0,mask=8) for y in range(32,192) for g in range(32)]
        self.assertEqual(cameras(rows,'nes',[1]),{1:[0]})
        with self.assertRaises(ValueError):cameras(rows[:-1],'nes',[1])
