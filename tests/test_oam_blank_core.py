import unittest
from tools.build_oam_blank_core import transform


class OamBlankCoreTests(unittest.TestCase):
    def test_only_hook_added(self):
        old='prefix\n\telse\n\t{\n\t\tconst uint16\tblack = BUILD_PIXEL(0, 0, 0);\nsuffix'
        new=transform(old)
        self.assertEqual(new.replace("\t\trcr_sprite_event('B', 255);\n",''),old)
        with self.assertRaises(ValueError):transform(new)

    def test_unknown_or_duplicate_anchor_rejected(self):
        for text in ('','\telse\n\t{\n\t\tconst uint16\tblack = BUILD_PIXEL(0, 0, 0);'*2):
            with self.assertRaises(ValueError):transform(text)
