import unittest
from pathlib import Path
from tools.check_fused_rows import expected, attribute_values
from tools.build_native import build


class FusedRowsTests(unittest.TestCase):
    def test_shadow_patterns_cover_all_attribute_values(self):
        self.assertEqual(attribute_values(),list(range(256)))

    def test_all_rows_leave_queued_aliases_untouched(self):
        old=bytes((i^(i>>8))&255 for i in range(8192))
        for row in range(128):
            if row%32>=30:continue
            for mirror in (0,1):
                alias=row^(32 if mirror else 64)
                for half in (0,16):
                    for state in range(4):
                        staging,flags=expected(row,mirror,half,state)
                        self.assertEqual(flags[row],2)
                        self.assertEqual(flags[alias],2 if state==1 else state)
                        self.assertEqual(staging[alias*64:(alias+1)*64],
                            staging[row*64:(row+1)*64] if state==1 else old[alias*64:(alias+1)*64])

    def test_missing_lookup_is_rejected_before_rom_access(self):
        with self.assertRaisesRegex(ValueError,'require attribute lookup'):
            build(Path('missing'),[],Path('unused'),experimental_fused_alias_rows=True)
