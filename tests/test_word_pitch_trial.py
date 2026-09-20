import copy
import unittest

from tests import test_balanced_pitch_trial
from tools.build_balanced_pitch_trial import patch as balanced
from tools.build_word_pitch_trial import patch
from tools.check_word_pitch_trial import compare_game, compare_writes


class WordPitchTests(unittest.TestCase):
    def fixture(self):
        old, layout = test_balanced_pitch_trial.BalancedPitchTests().fixture()
        return balanced(old, layout)[0], layout

    def test_only_checked_regions_change_and_word_write_is_present(self):
        old, layout = self.fixture()
        new, meta = patch(old, layout)
        self.assertEqual(len(old), len(new))
        allowed = set()
        for change in meta['changes']:
            at = change['offset']
            self.assertEqual(len(bytes.fromhex(change['after'])), 40)
            self.assertEqual(new[at+38:at+40], bytes.fromhex('daf2'))
            allowed.update(range(at, at+40))
        self.assertTrue(all(a == b or i in allowed for i, (a, b) in enumerate(zip(old, new))))
        with self.assertRaises(ValueError):
            patch(new, layout)

    def test_changed_preimage_or_caller_rejected(self):
        old, layout = self.fixture()
        for at in (12000, 12039, 12040, 12200, 12239, 12243):
            bad = bytearray(old)
            bad[at] ^= 1
            with self.subTest(at=at), self.assertRaises(ValueError):
                patch(bad, layout)

    def test_only_low_write_may_move_three_clocks(self):
        a = [dict(register=2, value=34, packet=1, tick=100),
             dict(register=3, value=2, packet=1, tick=108),
             dict(register=0, value=100, packet=1, tick=124)]
        b = copy.deepcopy(a)
        b[0]['tick'] += 3
        self.assertEqual(compare_writes(a, b)['shifts'], {3: 1, 0: 2})
        for index, key in ((0, 'tick'), (1, 'tick'), (2, 'tick'), (0, 'value'), (0, 'packet')):
            bad = copy.deepcopy(b)
            bad[index][key] += 1
            with self.subTest(index=index, key=key), self.assertRaises(ValueError):
                compare_writes(a, bad)
        with self.assertRaises(ValueError):
            compare_writes(a, b[:-1])

    def test_game_gate_retains_audio_callback_and_state_changes(self):
        a = [dict(frame=1, audio_start_sample=0, audio=dict(samples=534, peak=10),
                  video_sha256='abc', game_ram_hex='00', phase='walk')]
        b = copy.deepcopy(a)
        b[0]['audio']['peak'] = 12
        self.assertTrue(compare_game(a, b)['strict_passed'])
        for field, value in (('video_sha256', 'def'), ('game_ram_hex', '01'), ('phase', 'pause')):
            bad = copy.deepcopy(b)
            bad[0][field] = value
            result = compare_game(a, bad)
            self.assertFalse(result['strict_passed'])
            self.assertEqual(result['state_errors'][0]['fields'], [field])
        b[0]['audio']['samples'] += 1
        self.assertFalse(compare_game(a, b)['strict_passed'])
        self.assertEqual(len(compare_game(a, b)['callback_changes']), 1)
        with self.assertRaises(ValueError):
            compare_game(a, [])


if __name__ == '__main__':
    unittest.main()
