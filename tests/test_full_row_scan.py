import unittest
from pathlib import Path

from tools.build_full_row_scan import patch, SITE, PREIMAGE


class FullRowScanTests(unittest.TestCase):
    def test_only_scan_operand_and_checksum_change(self):
        original = Path('build/guarded-volume-game-3408/native-cpu.sfc').read_bytes()
        trial, changes = patch(original)
        self.assertEqual(trial[SITE:SITE+len(PREIMAGE)],
                         bytes.fromhex('a08000')+PREIMAGE[3:])
        self.assertIn(SITE+1, changes)
        self.assertTrue(all(i == SITE+1 or 0xFFDC <= i < 0xFFE0 for i in changes))
        self.assertEqual(original[0x120000:], trial[0x120000:])

    def test_wrong_parent_rejected(self):
        original = bytearray(Path('build/guarded-volume-game-3408/native-cpu.sfc').read_bytes())
        original[SITE+1] = 0
        with self.assertRaises(ValueError):
            patch(original)


if __name__ == '__main__':
    unittest.main()
