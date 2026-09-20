import unittest

from tools.build_compact_startup_pitch import sections, FLUSH, FINISH
from tools.build_balanced_startup_game import balance


class BalancedTests(unittest.TestCase):
    def test_no_restart_skips_only_validity_clear(self):
        data = bytearray(12415)
        for at, code in sections().items():
            data[at-0x400:at-0x400+len(code)] = code
        result, metadata = balance(bytes(data))
        rel = result[FLUSH-0x400+3]
        self.assertEqual(FLUSH+4+(rel-256 if rel >= 128 else rel), FINISH+5)
        self.assertEqual(result[FINISH-0x400+5:FINISH-0x400+12], bytes.fromhex('8f00548f7df46f'))
        changed = {i for i, (a, b) in enumerate(zip(data, result)) if a != b}
        self.assertTrue(changed <= set(range(FINISH-0x400, FINISH-0x400+12)) | {FLUSH-0x400+3})
        with self.assertRaises(ValueError):
            balance(result)


if __name__ == '__main__':
    unittest.main()
