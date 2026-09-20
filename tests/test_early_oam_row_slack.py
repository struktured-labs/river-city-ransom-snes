from pathlib import Path
import unittest
from tools.early_oam_row_slack import patch,SITE


class RowSlackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.parent=Path('build/early-oam-chr-game-3527/native-cpu.sfc').read_bytes()

    def test_only_row_cutoff_and_checksum_change(self):
        for cutoff in (250,251):
            data,changes=patch(self.parent,cutoff)
            self.assertEqual(data[SITE+3],cutoff)
            self.assertTrue(all(i==SITE+3 or 0xffdc<=i<0xffe0 for i in changes))
            self.assertEqual(data[0x86c1],246)
            self.assertEqual(data[0x86df],254)

    def test_wrong_parent_and_unbounded_deadline_rejected(self):
        bad=bytearray(self.parent);bad[SITE+3]^=1
        with self.assertRaises(ValueError):patch(bad,250)
        with self.assertRaises(ValueError):patch(self.parent,252)


if __name__=='__main__':unittest.main()
