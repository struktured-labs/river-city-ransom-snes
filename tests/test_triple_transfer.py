import unittest
from pathlib import Path

from tools.prepare_audio import triple_engine


class TripleTransferTests(unittest.TestCase):
    def source(self):
        return (Path(__file__).resolve().parents[1] /
                '.deps/upernes/source/asm/Memblers_2a03.bin').read_bytes()

    def test_checked_receiver_relocation(self):
        source = self.source()
        engine = triple_engine(source)
        self.assertEqual(len(engine), 0x2c1f)
        self.assertEqual(engine[0x87:0x8a], bytes.fromhex('5f0030'))
        self.assertEqual(engine[0x8a:0x96], source[0x8a:0x96])
        self.assertEqual(engine[0x2c00:], bytes.fromhex(
            '3ef4d0fce4f5d440e4f6d441e4f7d442'
            'd8f43d3d3dc818d0e71d5f96040000'))

    def test_triangle_control_changes_only_volume_fix(self):
        source = self.source()
        good = triple_engine(source)
        control = triple_engine(source, triangle_fix=False)
        changed = [i for i, pair in enumerate(zip(good, control)) if pair[0] != pair[1]]
        self.assertEqual(changed, [0x28e])

    def test_fast_reset_reuses_fixed_receiver_boundary(self):
        source = self.source()
        with self.assertRaises(ValueError):
            triple_engine(source, reset_notes=True)
        with self.assertRaises(ValueError):
            triple_engine(source, fast_reset=True)
        engine = triple_engine(source, reset_notes=True, fast_reset=True)
        self.assertEqual(len(engine), 0x2c7f)
        self.assertNotEqual((len(engine)-1) & 0xff, 0x7d)
        self.assertEqual(engine[0x2c1a:0x2c1d], bytes.fromhex('5f1f30'))
