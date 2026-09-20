import tempfile
import unittest
from pathlib import Path

from PIL import Image

from tools.benchmark_capture import scenario_for
from tools.check_shop_confirm import GLYPHS, REGION, _analyze


class ShopConfirmationAuditTests(unittest.TestCase):
    def test_route_selects_only_one_item_then_observes_prompt(self):
        phases = scenario_for('traversal-shop-confirm')
        self.assertEqual([phase['name'] for phase in phases[-4:]], [
            'shop_select_item', 'shop_confirm_idle_1', 'shop_confirm_idle_2',
            'shop_confirm_idle_3'])
        self.assertEqual(phases[-4]['buttons'], ['A'])
        self.assertTrue(all('buttons' not in phase for phase in phases[-3:]))

    def test_exact_glyphs_and_pixels_reject_missing_or_unpublished_prompt(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            reference, candidate = root/'nes', root/'snes'
            reference.mkdir()
            candidate.mkdir()
            original = [187, 216, 196, 210, 205, 206]
            for phase in ('shop_confirm_idle_1', 'shop_confirm_idle_2', 'shop_confirm_idle_3'):
                for path in (reference, candidate):
                    table = bytearray(2048)
                    pixels = Image.new('RGB', (256, 240 if path == reference else 239))
                    if phase != 'shop_confirm_idle_1':
                        for offset, glyph in zip(GLYPHS, original):
                            table[offset] = glyph
                        pixels.putpixel((REGION[0]+3, REGION[1]+3), (248, 248, 248))
                    (path/f'{phase}.nametable').write_bytes(table)
                    pixels.save(path/f'{phase}.png')
            vram = bytearray(65536)
            for offset, glyph in zip(GLYPHS, original):
                vram[(0x2000+offset)*2] = glyph
            (candidate/'shop_confirm_idle_3.vram').write_bytes(vram)
            self.assertTrue(_analyze(reference, candidate)['passed'])

            vram[(0x2000+GLYPHS[0])*2] = 0
            (candidate/'shop_confirm_idle_3.vram').write_bytes(vram)
            self.assertFalse(_analyze(reference, candidate)['passed'])
            vram[(0x2000+GLYPHS[0])*2] = original[0]
            (candidate/'shop_confirm_idle_3.vram').write_bytes(vram)

            table = bytearray((candidate/'shop_confirm_idle_3.nametable').read_bytes())
            table[GLYPHS[0]] = 0
            (candidate/'shop_confirm_idle_3.nametable').write_bytes(table)
            self.assertFalse(_analyze(reference, candidate)['passed'])
            table[GLYPHS[0]] = original[0]
            (candidate/'shop_confirm_idle_3.nametable').write_bytes(table)

            pixels = Image.open(candidate/'shop_confirm_idle_3.png').convert('RGB')
            pixels.putpixel((REGION[0]+3, REGION[1]+3), (0, 0, 0))
            pixels.save(candidate/'shop_confirm_idle_3.png')
            self.assertGreater(_analyze(reference, candidate)['phases'][-1]['mismatch_pixels'], 0)


if __name__ == '__main__':
    unittest.main()
