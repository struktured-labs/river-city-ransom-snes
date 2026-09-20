import unittest

from tools.audit_startup_pitch_game import cross_game, note_windows


class StartupGameTests(unittest.TestCase):
    def test_no_pitch_pair_requires_both_volumes_zero(self):
        events = [dict(voice=0, packet=1)]
        registers = [0]*128
        ready = {1: dict(tick=100, registers=registers)}
        checked, inactive = note_windows(events, [], ready)
        self.assertFalse(checked); self.assertEqual(len(inactive), 1)
        registers[1] = 1
        with self.assertRaisesRegex(ValueError, 'audible'):
            note_windows(events, [], ready)

    def test_all_cross_arm_differences_are_retained(self):
        first = dict(frame=1, audio_start_sample=0, audio=dict(samples=10), video_sha256='a', game_ram_hex='00')
        last = dict(first, audio_start_sample=1, video_sha256='b', game_ram_hex='01')
        result = cross_game([first], [last])
        self.assertFalse(result['exact_nonaudio_timeline_equal'])
        self.assertFalse(result['exact_callback_timeline_equal'])
        self.assertEqual(result['differences'][0]['fields'], ['game_ram_hex', 'video_sha256'])
        with self.assertRaisesRegex(ValueError, 'coverage'):
            cross_game([first], [])


if __name__ == '__main__':
    unittest.main()
