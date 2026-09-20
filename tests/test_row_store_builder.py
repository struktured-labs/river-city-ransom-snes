"""Ensure game builds can opt into the already oracle-covered row stores."""
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class RowStoreBuilderTests(unittest.TestCase):
    def test_lookup_path_honors_fixed_store_offsets(self):
        source = (ROOT / 'snes/native_prepare.asm').read_text()
        block = source.split('.macro attribute_lookup_group table,', 1)[1].split('.endmacro', 1)[0]
        self.assertIn('sta f:$7E3000 + pair*4 + tile*2,x', block)
        self.assertIn('.ifdef EXPERIMENTAL_ROW_STORES', block)
        caller = source.split('.macro attribute_lookup_groups table,', 1)[1].split('.endmacro', 1)[0]
        self.assertIn('attribute_lookup_group table, alias_delta, 0', caller)

    def test_builder_exposes_explicit_experimental_flag(self):
        source = (ROOT / 'tools/build_native.py').read_text()
        self.assertIn("'EXPERIMENTAL_ROW_STORES=1'", source)
        self.assertIn("'--experimental-row-stores'", source)


if __name__ == '__main__':
    unittest.main()
