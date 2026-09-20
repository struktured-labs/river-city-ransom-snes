import unittest
from pathlib import Path

from tools.prepare_audio import paired_engine, suppress_duty_keyons


class DutyKeyonSuppressionTests(unittest.TestCase):
    def source(self):
        return (Path(__file__).resolve().parents[1] /
                '.deps/upernes/source/asm/Memblers_2a03.bin').read_bytes()

    def test_only_both_hard_keyons_are_removed(self):
        parent = paired_engine(self.source())
        candidate = suppress_duty_keyons(parent)
        changed = [i for i, pair in enumerate(zip(parent, candidate)) if pair[0] != pair[1]]
        self.assertEqual(changed, [0xC3, 0xC4, 0x1A5, 0x1A6])
        self.assertEqual(candidate[0xB9:0xBF], parent[0xB9:0xBF])
        self.assertEqual(candidate[0x19B:0x1A1], parent[0x19B:0x1A1])
        self.assertEqual(candidate[0xBF:0xC5], bytes.fromhex('8f4cf28f0054'))
        self.assertEqual(candidate[0x1A1:0x1A7], bytes.fromhex('8f4cf28f0054'))

    def test_mutated_preimage_is_rejected(self):
        engine = bytearray(paired_engine(self.source()))
        engine[0x1A1] ^= 1
        with self.assertRaises(ValueError):
            suppress_duty_keyons(engine)


if __name__ == '__main__':
    unittest.main()
