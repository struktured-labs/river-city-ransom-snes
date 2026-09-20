import copy
import unittest

from tools.audit_camera_hold_origin import classify
from tools.audit_display_cadence import measure


class CameraHoldOriginTests(unittest.TestCase):
    def fixture(self):
        work = [dict(start=dict(frame=f-1), commit=dict(frame=f, camera=c))
                for f, c in ((1, 1), (3, 1), (5, 2))]
        series = [dict(frame=f, camera=0 if f == 1 else 1 if f < 6 else 2)
                  for f in range(1, 8)]
        return {'park': measure(series)}, work

    def test_repeated_command_not_missed_main(self):
        result = classify(*self.fixture())[0]
        self.assertEqual(result['hold']['frames'], 4)
        self.assertEqual(result['classification'], 'repeated_command_with_regular_main')

    def test_missing_main_not_cleared(self):
        phases, work = self.fixture()
        del work[1]
        result = classify(phases, work)[0]
        self.assertFalse(result['two_frame_main_cadence'])
        self.assertEqual(result['classification'], 'not_explained_by_repeated_command')

    def test_unpublished_intermediate_camera_not_cleared(self):
        phases, work = self.fixture()
        work[1]['commit']['camera'] = 2
        result = classify(phases, work)[0]
        self.assertFalse(result['all_stores_visible_next_frame'])
        self.assertEqual(result['classification'], 'not_explained_by_repeated_command')

    def test_boundary_retained(self):
        phases, work = self.fixture()
        self.assertEqual(classify(phases, work[1:])[0]['classification'], 'outside_main_window')

    def test_changed_derived_interval_rejected(self):
        phases, work = self.fixture()
        phases['park']['intervals'][0]['frames'] = 2
        with self.assertRaisesRegex(ValueError, 'derivation'):
            classify(phases, work)

    def test_duplicate_main_rejected(self):
        phases, work = self.fixture()
        work.insert(1, copy.deepcopy(work[0]))
        with self.assertRaisesRegex(ValueError, 'ordered'):
            classify(phases, work)


if __name__ == '__main__':
    unittest.main()
