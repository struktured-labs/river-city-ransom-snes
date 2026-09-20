import unittest
from pathlib import Path

from tools.early_oam_scan import patch as old_patch, OAM, HELPER
from tools.early_oam_palette import patch


class EarlyOamTests(unittest.TestCase):
    def test_exact_transfer_moved_and_palette_preconditions_restored(self):
        parent=Path('build/guarded-volume-game-3408/native-cpu.sfc').read_bytes()
        old,_=old_patch(parent);new,_=patch(parent)
        self.assertEqual(new[HELPER:HELPER+len(OAM)],OAM)
        self.assertEqual(new[0x82b6:0x82bb],bytes.fromhex('200073eaea'))
        self.assertEqual(new[0x8464:0x846f],bytes.fromhex('9c0043a97e8d04434c8884'))
        self.assertNotEqual(old[0x8464:0x846f],new[0x8464:0x846f])
        self.assertEqual(new[0x8800],249)
        self.assertEqual(new[0x120000:],parent[0x120000:])

    def test_unrelated_parent_mutation_rejected(self):
        parent=bytearray(Path('build/guarded-volume-game-3408/native-cpu.sfc').read_bytes())
        parent[0x7000]^=1
        with self.assertRaises(ValueError):patch(parent)


if __name__=='__main__':unittest.main()
