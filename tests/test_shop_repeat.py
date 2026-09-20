import tempfile
import unittest
from pathlib import Path

from PIL import Image

from tools.benchmark_capture import scenario_for
from tools.check_shop_repeat import GLYPHS, PHASES, PROMPT_PHASES, REGION, _analyze


class ShopRepeatAuditTests(unittest.TestCase):
    def test_route_releases_each_press_and_reaches_second_purchase(self):
        phases = scenario_for('traversal-shop-repeat')
        names = [phase['name'] for phase in phases]
        self.assertLess(names.index('shop_accept_yes'), names.index('shop_second_confirm'))
        self.assertLess(names.index('shop_second_confirm'), names.index('shop_accept_second'))
        self.assertEqual(names[-1], 'shop_after_purchase_5')
        for before, after in (('shop_accept_yes', 'shop_after_purchase_1'),
                              ('shop_select_second', 'shop_second_confirm'),
                              ('shop_accept_second', 'shop_after_purchase_5')):
            self.assertEqual(phases[names.index(before)]['buttons'], ['A'])
            self.assertNotIn('buttons', phases[names.index(after)])

    def test_rejects_stuck_prompt_missing_reappearance_or_unpublished_vram(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            reference, candidate = root/'nes', root/'snes'
            reference.mkdir()
            candidate.mkdir()
            glyphs = (187, 216, 196, 210, 205, 206)
            for phase in PHASES:
                for path in (reference, candidate):
                    table = bytearray(2048)
                    vram = bytearray(65536)
                    pixels = Image.new('RGB', (256, 240 if path == reference else 239))
                    if phase in PROMPT_PHASES:
                        for offset, glyph in zip(GLYPHS, glyphs):
                            table[offset] = glyph
                            vram[(0x2000+offset)*2] = glyph
                        pixels.putpixel((REGION[0]+3, REGION[1]+3), (248, 248, 248))
                    (path/f'{phase}.nametable').write_bytes(table)
                    (path/f'{phase}.vram').write_bytes(vram)
                    pixels.save(path/f'{phase}.png')
            self.assertTrue(_analyze(reference, candidate)['passed'])

            table = bytearray((candidate/'shop_after_purchase_1.nametable').read_bytes())
            table[GLYPHS[0]] = glyphs[0]
            (candidate/'shop_after_purchase_1.nametable').write_bytes(table)
            self.assertFalse(_analyze(reference, candidate)['passed'])
            table[GLYPHS[0]] = 0
            (candidate/'shop_after_purchase_1.nametable').write_bytes(table)

            vram = bytearray((candidate/'shop_second_confirm.vram').read_bytes())
            vram[(0x2000+GLYPHS[0])*2] = 0
            (candidate/'shop_second_confirm.vram').write_bytes(vram)
            self.assertFalse(_analyze(reference, candidate)['passed'])
            vram[(0x2000+GLYPHS[0])*2] = glyphs[0]
            (candidate/'shop_second_confirm.vram').write_bytes(vram)

            pixels = Image.open(candidate/'shop_after_purchase_5.png').convert('RGB')
            pixels.putpixel((REGION[0]+3, REGION[1]+3), (248, 248, 248))
            pixels.save(candidate/'shop_after_purchase_5.png')
            self.assertFalse(_analyze(reference, candidate)['passed'])


if __name__ == '__main__':
    unittest.main()
