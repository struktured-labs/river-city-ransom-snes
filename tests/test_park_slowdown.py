"""A real park hitch must fail; an intentional pause never masquerades as one."""
import unittest

import numpy as np

from tools.audit_park_slowdown import evaluate


class ParkSlowdownTests(unittest.TestCase):
    @staticmethod
    def encounter(hitch=False):
        rows = [{'changed_pixels_40': 85 if i % 2 else 0,
                 'park_green_ratio': .43} for i in range(1200)]
        menu = [{'pause_menu': 600 <= i < 720} for i in range(1200)]
        for i in range(600,720):
            rows[i]['changed_pixels_40'] = 0
        if hitch:
            for i in range(250,259):
                rows[i]['changed_pixels_40'] = 0
        rms = np.full(1000, 480.0)
        rms[600*50//60:720*50//60] = 0
        return rows, menu, rms

    def test_pause_is_covered_but_not_a_game_performance_failure(self):
        rows, menu, rms = self.encounter()
        report = evaluate(rows,rms,2820,0,20,menu,require_pause=True)
        self.assertTrue(report['coverage_passed'])
        self.assertTrue(report['performance_passed'])
        self.assertTrue(any(s['category']=='menu_overlaps'
                            for s in report['video_stalls_needing_review']))
        self.assertEqual(report['post_menu_resume'][0]['no_game_motion_after_close_ms'],17)

    def test_nine_missing_active_game_frames_fail_regression(self):
        rows, menu, rms = self.encounter(hitch=True)
        report = evaluate(rows,rms,2820,0,20,menu)
        self.assertTrue(report['coverage_passed'])
        self.assertFalse(report['performance_passed'])
        self.assertEqual(report['video_stalls_needing_review'][0]['category'],'active_encounter')
        self.assertGreaterEqual(report['video_stalls_needing_review'][0]['duration_video_frames'],9)
        self.assertGreater(report['video_stalls_needing_review'][0]['audio_median_rms_pcm'],400)

    def test_250ms_audio_blackout_during_combat_fails_independently(self):
        rows, menu, rms = self.encounter()
        rms[150:163] = 0  # 260ms, far from the pause UI
        report = evaluate(rows,rms,2820,0,20,menu)
        self.assertTrue(report['gates']['no_eight_frame_active_park_stall'])
        self.assertFalse(report['gates']['no_unpaused_200ms_audio_blackout'])
        self.assertEqual(report['unpaused_audio_blackouts'][0]['duration_ms'],260)

    def test_pause_overlay_does_not_hide_long_unpaused_frozen_lead(self):
        rows, menu, rms = self.encounter()
        for i in range(580,600):
            rows[i]['changed_pixels_40'] = 0
        report = evaluate(rows,rms,2820,0,20,menu)
        self.assertFalse(report['gates']['no_eight_frame_unpaused_lead_into_menu'])
        self.assertEqual([s for s in report['video_stalls_needing_review']
                          if s['category']=='menu_overlaps'][0]
                         ['unpaused_lead_into_menu_frames'],20)

    def test_missing_pause_observer_cannot_certify_video_stall(self):
        rows, menu, rms = self.encounter()
        with self.assertRaisesRegex(ValueError,'pause UI'):
            evaluate(rows,rms,2820,0,20)
        with self.assertRaisesRegex(ValueError,'pause UI'):
            evaluate(rows,rms,2820,0,20,menu[:10])

    def test_other_park_encounter_without_menu_is_still_a_valid_fixture(self):
        rows, menu, rms = self.encounter()
        menu = [{'pause_menu':False} for _ in menu]
        for frame in rows:
            frame['changed_pixels_40'] = 90
        report = evaluate(rows,rms,2820,0,20,menu)
        self.assertTrue(report['coverage_passed'])
        self.assertFalse(evaluate(rows,rms,2820,0,20,menu,
                                  require_pause=True)['coverage_passed'])


if __name__=='__main__':
    unittest.main()
