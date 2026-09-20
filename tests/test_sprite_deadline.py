import unittest

from tools.review_sprite_deadline import cadence


def rows(values):
    result = []
    for frame, value in enumerate(values, 1):
        ram = bytearray(2048)
        ram[0x52b] = value
        result.append(dict(frame=frame, game_ram_hex=ram.hex()))
    return result


class SpriteDeadlineTests(unittest.TestCase):
    def test_boundary_not_invented_and_counter_wrap_allowed(self):
        result = cadence(rows([254, 254, 255, 255, 0, 0, 1]))
        self.assertEqual(result['completions'], [3, 5, 7])
        self.assertEqual(result['histogram'], {2: 2})
        self.assertTrue(result['all_two_frames'])

    def test_retains_three_frame_stall(self):
        result = cadence(rows([0, 1, 1, 2, 2, 2, 3]))
        self.assertEqual(result['histogram'], {2: 1, 3: 1})
        self.assertFalse(result['all_two_frames'])

    def test_skipped_counter_or_missing_frame_rejected(self):
        with self.assertRaises(ValueError):
            cadence(rows([0, 1, 3]))
        with self.assertRaises(ValueError):
            cadence(rows([0, 1, 1, 2])[::2])

    def test_frozen_counter_not_success(self):
        self.assertFalse(cadence(rows([4, 4, 4, 4]))['all_two_frames'])
