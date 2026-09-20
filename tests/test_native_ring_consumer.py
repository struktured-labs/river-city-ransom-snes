import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class NativeRingConsumerTests(unittest.TestCase):
    def test_whole_consumer_is_opt_in_and_preimage_checked(self):
        source = (ROOT/'tools/build_native.py').read_text()
        self.assertIn('--experimental-native-ring-consumer', source)
        self.assertIn("consumer_offset = 0x1C50B", source)
        self.assertIn("consumer_preimage = bytes.fromhex('a50448a001ad3e002902d002a0048404')", source)
        self.assertIn("b'\\x4c' + word(symbols['native_ring_consumer'])", source)

    def test_native_path_preserves_budget_read_and_tail_contracts(self):
        source = (ROOT/'snes/native_runtime.asm').read_text()
        block = source.split('.ifdef EXPERIMENTAL_NATIVE_RING_CONSUMER', 1)[1].split('bank_switch_enter:', 1)[0]
        for text in ('lda a:$003E', 'ldy #4', 'dec a:$0004',
                     'jsr ppu_read_buffer', 'sta a:$0000,y',
                     'stx a:$06B6', 'stz a:$1C26', 'stz a:$1C27'):
            self.assertIn(text, block)

    def test_executed_fixture_has_mutation_control(self):
        source = (ROOT/'tools/check_native_ring_consumer.py').read_text()
        self.assertIn("image.count(pointer_store) != 16", source)
        self.assertIn('adapter case=32', source)


if __name__ == '__main__':
    unittest.main()
