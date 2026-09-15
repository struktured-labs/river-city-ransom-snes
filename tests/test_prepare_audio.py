import unittest
from pathlib import Path
from tools.prepare_audio import prepare_engine


class PrepareAudioTests(unittest.TestCase):
    def test_unknown_engine_rejected(self):
        with self.assertRaises(ValueError):
            prepare_engine(bytes(0x2c00))

    def test_pinned_patch_changes_only_address_operand(self):
        path = Path('.deps/upernes/source/asm/Memblers_2a03.bin')
        if not path.exists():
            self.skipTest('Pinned dependency not installed')
        original = path.read_bytes()
        patched = prepare_engine(original)
        self.assertEqual(len(patched), len(original))
        self.assertEqual([i for i, (a, b) in enumerate(zip(original, patched)) if a != b], [0x28e])
        self.assertEqual(patched[0x28e], 0xf2)
        with self.assertRaises(ValueError):
            prepare_engine(patched)
