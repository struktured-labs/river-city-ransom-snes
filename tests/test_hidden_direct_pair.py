import inspect
from pathlib import Path
import unittest
from tools.build_native import build
from tools.check_hidden_high_cache import expected, initial_flags
from tools.check_rows import expected_rows


class HiddenDirectPairTests(unittest.TestCase):
    def test_default_off_and_dependency(self):
        self.assertIs(inspect.signature(build).parameters['experimental_hidden_direct_pair'].default, False)
        with self.assertRaisesRegex(ValueError, 'require hidden high cache'):
            build(Path('missing'), [], Path('unused'), experimental_hidden_direct_pair=True)

    def test_even_odd_high_bytes_are_identical_in_both_mirroring_modes(self):
        shadow = bytes((i ^ (i >> 8)) & 255 for i in range(4096))
        for mirror in (0, 1):
            for half in (0, 16):
                tiles = expected_rows(shadow, half, mirror)
                for row in range(0, 128, 2):
                    if row % 32 < 30:
                        self.assertEqual(tiles[row*64+1:(row+1)*64:2],
                                         tiles[(row+1)*64+1:(row+2)*64:2])

    def test_one_row_budget_cannot_retire_the_neighbor(self):
        shadow = bytes(4096)
        flags = initial_flags(0, 0)
        _, after, _, retired = expected(shadow, flags, 0, 0, 0, 1)
        self.assertNotIn(1, retired)
        self.assertEqual(after[1], 1)
