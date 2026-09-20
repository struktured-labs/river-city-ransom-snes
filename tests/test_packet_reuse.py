import unittest
from pathlib import Path

from tools.prepare_audio import paired_engine


class PacketReuseTests(unittest.TestCase):
    def source(self):
        return (Path(__file__).resolve().parents[1] /
                '.deps/upernes/source/asm/Memblers_2a03.bin').read_bytes()

    def test_checked_idle_redirect_and_command_body(self):
        source = self.source()
        engine = paired_engine(source, reuse_packet=True)
        self.assertEqual(len(engine), 0x2c37)
        self.assertEqual(engine[0x7d:0x87], bytes.fromhex('5f003000000000000000'))
        self.assertEqual(engine[0x2c00:0x2c11],
                         bytes.fromhex('e4f468d7f00768d6f0265f7404c4f4cd00'))
        self.assertEqual(engine[-7:], bytes.fromhex('c4f4cd175f9604'))

    def test_reset_combination_is_explicitly_rejected(self):
        with self.assertRaises(ValueError):
            paired_engine(self.source(), reset_notes=True, reuse_packet=True)
