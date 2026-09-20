import unittest
from tools.audit_pacing_case import spacing,first_new_display


class PacingCaseTests(unittest.TestCase):
    def test_repeated_stationary_camera_is_not_a_new_display(self):
        with self.assertRaisesRegex(ValueError,'already displayed'):
            first_new_display({9:{32:87},10:{32:87},11:{32:87}},10,87,11)

    def test_new_display_can_be_same_frame_or_delayed(self):
        self.assertEqual(first_new_display({9:{32:85},10:{32:87}},10,87,10),10)
        self.assertEqual(first_new_display({9:{32:85},10:{32:85},11:{32:87}},10,87,11),11)

    def test_missing_split_and_never_displayed_fail_closed(self):
        for rendered in ({10:{32:87}}, {9:{32:85},11:{32:87}},
                         {9:{32:85},10:{32:85,33:87}},
                         {9:{32:85},10:{32:85},11:{32:85}}):
            with self.subTest(rendered=rendered),self.assertRaises(ValueError):
                first_new_display(rendered,10,87,11)

    def test_measured_regression_and_regular_control(self):
        events=[dict(frame=f,camera=c,display_frame=d) for f,c,d in ((10,20,11),(12,22,12),(14,24,15))]
        self.assertFalse(spacing(events)['uniform_presentation'])
        events[1]['display_frame']=13
        self.assertTrue(spacing(events)['uniform_presentation'])

    def test_variable_producer_is_not_called_fixed_cadence(self):
        events=[dict(frame=f,camera=c,display_frame=f+1) for f,c in ((10,20),(12,22),(14,26))]
        with self.assertRaises(ValueError):spacing(events)
        events[-1]['camera']=24;events[-1]['frame']=15
        with self.assertRaises(ValueError):spacing(events)

    def test_variable_producer_evidence_remains_nonuniform(self):
        events=[dict(frame=f,camera=c,display_frame=f+1) for f,c in ((10,20),(13,22),(14,24))]
        result=spacing(events,variable_producer=True)
        self.assertEqual(result['producer_frame_intervals'],[3,1])
        self.assertTrue(result['presentation_tracks_producer'])
        self.assertFalse(result['uniform_production'])
        self.assertFalse(result['uniform_presentation'])

    def test_nonincreasing_producer_is_not_accepted_as_variable(self):
        events=[dict(frame=f,camera=c,display_frame=f+1) for f,c in ((10,20),(10,22),(14,24))]
        with self.assertRaisesRegex(ValueError,'increase'):
            spacing(events,variable_producer=True)
