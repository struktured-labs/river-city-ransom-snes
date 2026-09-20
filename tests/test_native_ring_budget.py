"""Structural guards for the forced-blank five-command ring experiment."""
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class NativeRingBudgetTests(unittest.TestCase):
    def test_fifth_command_is_transition_only(self):
        source = (ROOT / 'snes/native_runtime.asm').read_text()
        block = source.split('native_ring_consumer:', 1)[1].split('@save_budget:', 1)[0]
        self.assertIn('ldy #4', block)
        self.assertIn('.ifdef EXPERIMENTAL_NATIVE_RING_BUDGET5', block)
        self.assertIn('lda a:$1CA0\n    beq @save_budget\n    iny', block)

    def test_builder_requires_native_consumer_and_records_flag(self):
        source = (ROOT / 'tools/build_native.py').read_text()
        self.assertIn('experimental_native_ring_budget5 and not experimental_native_ring_consumer', source)
        self.assertIn("'EXPERIMENTAL_NATIVE_RING_BUDGET5=1'", source)
        self.assertIn('"experimental_native_ring_budget5": experimental_native_ring_budget5', source)


if __name__ == '__main__':
    unittest.main()
