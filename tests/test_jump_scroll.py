from copy import deepcopy
import unittest

import numpy as np

from tools import benchmark_capture as bench
from tools.audit_jump_scroll import changes, picture_changes
from tools.capture_jump_scroll import NAME, registered, scenario
from tools.audit_physical_hold_context import difference


class JumpScrollTests(unittest.TestCase):
    def samples(self):
        return [dict(frame=i+1, phase='jump_right', room=0, camera=2*(i//2)) for i in range(16)]

    def test_episode_uses_same_logical_jump_and_bounded_holds(self):
        right, left = scenario()[-3:-1]
        self.assertEqual([right['frames'], left['frames']], [960, 240])
        for phase, direction in [(right, 'Right'), (left, 'Left')]:
            self.assertEqual(phase['buttons'], [direction, 'A', 'B'])
            self.assertEqual(phase['hold_buttons'], [direction])
            self.assertEqual(phase['pulse'], [30, 18])

    def test_registry_restored_even_on_failure(self):
        original = bench.scenario_for
        with self.assertRaises(RuntimeError):
            with registered():
                self.assertEqual(bench.scenario_for(NAME), scenario())
                self.assertEqual(bench.scenario_for('baseline'), original('baseline'))
                raise RuntimeError('aborted capture')
        self.assertIs(bench.scenario_for, original)

    def test_cadence_detects_duplicate_and_keeps_long_stop(self):
        baseline = self.samples()
        self.assertEqual(changes(baseline, 'camera')['histogram'], {2: 6})
        for count in (1, 2, 12):
            mutant = deepcopy(baseline[:8] + [baseline[7]] * count + baseline[8:])
            # Reassign separately: repeated values must not alias during mutation.
            mutant = [dict(row, frame=i+1) for i, row in enumerate(mutant)]
            result = changes(mutant, 'camera')
            self.assertIn(2+count, result['histogram'])

    def test_missing_frames_and_room_boundaries_are_not_bridged(self):
        baseline = self.samples()
        broken = baseline[:8] + baseline[9:]
        self.assertNotIn(4, changes(broken, 'camera')['histogram'])
        split = [dict(row, room=int(i >= 8)) for i, row in enumerate(baseline)]
        self.assertEqual(len(changes(split, 'camera')['events']), 6)

    def test_picture_rejection_censors_interval(self):
        samples = self.samples()
        pairs = [dict(frame=r['frame'], accepted=True, camera_delta=2 if i and i % 2 == 0 else 0)
                 for i, r in enumerate(samples)]
        self.assertEqual(picture_changes(samples, pairs)['histogram'], {2: 6})
        pairs[7]['accepted'] = False
        result = picture_changes(samples, pairs)
        self.assertEqual(result['histogram'], {2: 4})
        self.assertFalse(result['short_irregular'])

    def test_region_motion_is_descriptive_and_does_not_unsigned_wrap(self):
        before = np.full((8, 8, 3), 255, dtype=np.uint8)
        after = before.copy()
        after[4:6, 4:6] = 0
        self.assertEqual(difference(before, after, (4, 4, 2, 2))['mean_absolute_channel_difference'], 255)
        self.assertEqual(difference(before, after, (0, 0, 8, 8))['pixels_changed_by_at_least_32'], 4)
        self.assertEqual(difference(before, after, (0, 0, 4, 4))['pixels_changed_by_at_least_32'], 0)
        with self.assertRaises(ValueError):
            difference(before, after, (0, 0, 9, 9))


if __name__ == '__main__':
    unittest.main()
