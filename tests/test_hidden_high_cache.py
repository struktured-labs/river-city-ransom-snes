import inspect
from pathlib import Path
import unittest
from tools.build_native import build
from tools.check_hidden_high_cache import initial_flags,expected


class HiddenHighCacheTests(unittest.TestCase):
    def test_default_off_and_dependency(self):
        self.assertIs(inspect.signature(build).parameters['experimental_hidden_high_cache'].default,False)
        with self.assertRaisesRegex(ValueError,'Hidden high cache requires'):
            build(Path('missing'),[],Path('unused'),experimental_hidden_high_cache=True)

    def test_expected_retirement_and_immutable_flags(self):
        shadow=bytes((i^(i>>8))&255 for i in range(4096))
        for start in range(128):
            for mirror in (0,1):
                flags=initial_flags(start,mirror)
                vram,after,requirements,retired=expected(shadow,flags,start,mirror,16,10)
                self.assertTrue(all(r%32<30 and flags[r]==1 for r in retired))
                self.assertEqual(len(retired),len(set(retired)))
                for row in range(128):
                    self.assertEqual(requirements[row],1 if row in retired else 2)
                    if flags[row] in (2,3):self.assertEqual(after[row],flags[row])
                    if row not in retired:self.assertEqual(vram[row*64:(row+1)*64],bytes.fromhex('5aa5')*32)
