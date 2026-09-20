import unittest

from tools.check_startup_pitch_state import state_hash


class StateTests(unittest.TestCase):
    def test_only_two_mmio_shadows_are_exempt(self):
        original = [0]*384
        for index in range(384):
            changed = original.copy(); changed[index] = 1
            with self.subTest(index=index):
                self.assertEqual(state_hash(original) == state_hash(changed), index in (0xf2, 0xf3))


if __name__ == '__main__':
    unittest.main()
