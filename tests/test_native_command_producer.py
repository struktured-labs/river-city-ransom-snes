"""Structural guards for the exact CF04 command producer replacement."""
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class NativeCommandProducerTests(unittest.TestCase):
    def test_helper_retains_six_ordered_stores_and_wraps(self):
        source = (ROOT / 'snes/native_runtime.asm').read_text()
        block = source.split('native_command_producer:', 1)[1].split(
            '.ifdef EXPERIMENTAL_NATIVE_RING_CONSUMER', 1)[0]
        self.assertEqual(block.count('sta a:$0545,x'), 6)
        self.assertEqual(block.count('command_producer_advance'), 6)
        self.assertIn('ldx a:$06B7', block)
        self.assertIn('stx a:$06B7\n    rts', block)
        self.assertEqual(block.count('pha'), 5)
        self.assertEqual(block.count('pla'), 2)

    def test_builder_checks_complete_original_routine(self):
        source = (ROOT / 'tools/build_native.py').read_text()
        self.assertIn('producer_offset = 0x1CF04', source)
        self.assertIn("symbols['native_command_producer']", source)
        self.assertIn('producer_offset + len(producer_preimage)', source)
        self.assertIn('"experimental_native_command_producer": experimental_native_command_producer', source)
        self.assertIn("'--experimental-native-command-producer'", source)


if __name__ == '__main__':
    unittest.main()
