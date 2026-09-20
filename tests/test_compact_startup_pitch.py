import unittest

from tools.build_compact_startup_pitch import sections, relative, patch, STAGE, ORDINARY, FINISH, VALID, FLUSH


class CompactTests(unittest.TestCase):
    def test_fixed_sections_and_retained_receiver(self):
        result = sections()
        self.assertEqual([len(result[a]) for a in STAGE], [21, 21])
        self.assertEqual((len(result[FLUSH]), len(result[FINISH]), len(result[VALID])), (61, 11, 5))
        for voice in (0, 1):
            rel = result[STAGE[voice]][5]
            signed = rel if rel < 128 else rel-256
            self.assertEqual(STAGE[voice]+6+signed, ORDINARY[voice])
        occupied = {i for a, b in result.items() for i in range(a, a+len(b))}
        self.assertFalse(occupied & set(range(0x2fa0, 0x2faa)))
        self.assertLess(max(occupied), 0x3000)

    def test_branch_and_preimage_guards(self):
        with self.assertRaisesRegex(ValueError, 'range'):
            relative(0x3000, 0, 0x4000)
        with self.assertRaisesRegex(ValueError, 'exact current'):
            patch(bytes(12415), {})


if __name__ == '__main__':
    unittest.main()
