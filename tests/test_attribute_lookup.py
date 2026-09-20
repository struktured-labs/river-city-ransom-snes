"""Static coverage for the row attribute lookup experiment and its oracle."""
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class AttributeLookupTests(unittest.TestCase):
    def test_all_four_attribute_quadrants_are_generated(self):
        source = (ROOT / 'snes/native_prepare.asm').read_text()
        block = source.split('attribute_palette_top:', 1)[1].split('native_palette:', 1)[0]
        for shift in (0, 2, 4, 6):
            self.assertIn(f'(attribute >> {shift})' if shift else '(attribute & 3)', block)
        self.assertIn('ora $0A + pair*2', source)

    def test_executed_oracle_has_lookup_negative_control(self):
        source = (ROOT / 'tools/check_rows.py').read_text()
        self.assertIn("bad = '(((attribute >> 0) & 3) << 10)'", source)
        self.assertIn("'EXPERIMENTAL_ATTRIBUTE_LOOKUP=1'", source)


if __name__ == '__main__':
    unittest.main()
