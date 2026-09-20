from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from tools.stage_mister_packet_seed import save_path, stage


class MisterPacketSeedTests(unittest.TestCase):
    def test_hash_named_save_path(self):
        self.assertEqual(save_path('a' * 64), '/media/fat/saves/SNES/RCR-SNES-aaaaaaaaaaaa.sav')

    def test_path_rejects_arbitrary_names_and_shell_text(self):
        for value in ('', 'a' * 63, 'a' * 65, '../file', 'A' * 64, ';' * 64):
            with self.subTest(value=value), self.assertRaises(ValueError):
                save_path(value)

    def test_existing_receipt_rejected_before_network(self):
        with TemporaryDirectory() as directory:
            receipt = Path(directory) / 'receipt.json'
            receipt.write_text('keep')
            with patch('tools.stage_mister_packet_seed.subprocess.run') as remote:
                with self.assertRaisesRegex(ValueError, 'fresh'):
                    stage(Path('/missing'), Path('/missing'), receipt)
                remote.assert_not_called()
            self.assertEqual(receipt.read_text(), 'keep')


if __name__ == '__main__':
    unittest.main()
