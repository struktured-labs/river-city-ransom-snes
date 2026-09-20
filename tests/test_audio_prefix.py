import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from tools.capture_audio_prefix import compare_full_prefix, LAST_PHASE
from tools.capture_sprite_prefix import installed_prefix
from tools import benchmark_capture as bench


class AudioPrefix(unittest.TestCase):
    def test_exact_image_derived_field(self):
        short = [dict(frame=1, frame_image='frame.png', video_sha256='same')]
        full = [dict(short[0], waypoint_cursor=[7]), dict(frame=2)]
        policy = MagicMock()
        policy.cursor_mask.return_value = (7,)
        with patch('tools.capture_audio_prefix.bench.waypoint_policy', return_value=policy), \
             patch('tools.capture_audio_prefix.Image.open'):
            compare_full_prefix(short, full, Path('/unused'))
            for field, value in [('waypoint_cursor', 8), ('video_sha256', 'changed')]:
                bad = [dict(full[0], **{field: value}), full[1]]
                with self.subTest(field=field), self.assertRaises(ValueError):
                    compare_full_prefix(short, bad, Path('/unused'))

    def test_prefix_is_explicit_and_restores(self):
        original = bench.scenario_for
        full = original('traversal-park-single-sweep')
        end = next(i for i, p in enumerate(full) if p['name'] == LAST_PHASE)
        with installed_prefix(LAST_PHASE):
            self.assertEqual(bench.scenario_for('traversal-park-single-sweep'), full[:end+1])
        self.assertIs(bench.scenario_for, original)

    def test_reject_not_a_prefix(self):
        for a, b in [([], [dict(frame=1)]), ([dict(frame=1)], [dict(frame=1)])]:
            with self.assertRaises(ValueError):
                compare_full_prefix(a, b, Path('/unused'))
