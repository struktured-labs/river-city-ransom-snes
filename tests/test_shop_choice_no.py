import tempfile
import unittest
from pathlib import Path

from PIL import Image

from tools.benchmark_capture import scenario_for
from tools.check_shop_choice_no import CURSORS, OFFSETS, PHASES, REGION, _analyze


class ShopNoAuditTests(unittest.TestCase):
    def test_route_changes_approves_only_after_returning_to_no(self):
        phases = scenario_for('traversal-shop-no')
        names = [phase['name'] for phase in phases]
        for phase, direction in (('shop_choose_no', 'Right'),
                                 ('shop_choose_yes_again', 'Left'),
                                 ('shop_choose_no_again', 'Right'),
                                 ('shop_confirm_no', 'A')):
            self.assertEqual(phases[names.index(phase)]['buttons'], [direction])
        self.assertEqual(names[-1], 'shop_no_result')
        self.assertNotIn('buttons', phases[-1])

    def test_rejects_stale_cursor_and_unpublished_vram(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            nes, snes = root/'nes', root/'snes'
            nes.mkdir()
            snes.mkdir()
            for phase, state in PHASES:
                for folder in (nes, snes):
                    table = bytearray(2048)
                    video = bytearray(65536)
                    pixels = Image.new('RGB', (256, 240 if folder == nes else 239))
                    if state != 'clear':
                        cursor = CURSORS[0] if state == 'yes' else CURSORS[1]
                        table[cursor] = 187
                        video[(0x2000+cursor)*2] = 187
                        pixels.putpixel((REGION[0]+3, REGION[1]+3), (248, 248, 248))
                    (folder/f'{phase}.nametable').write_bytes(table)
                    (folder/f'{phase}.vram').write_bytes(video)
                    pixels.save(folder/f'{phase}.png')
            self.assertTrue(_analyze(nes, snes)['passed'])

            phase = 'shop_no_idle'
            shadow = bytearray((snes/f'{phase}.nametable').read_bytes())
            shadow[CURSORS[1]] = 0
            (snes/f'{phase}.nametable').write_bytes(shadow)
            self.assertFalse(_analyze(nes, snes)['passed'])
            shadow[CURSORS[1]] = 187
            (snes/f'{phase}.nametable').write_bytes(shadow)

            video = bytearray((snes/f'{phase}.vram').read_bytes())
            video[(0x2000+CURSORS[1])*2] = 0
            (snes/f'{phase}.vram').write_bytes(video)
            self.assertFalse(_analyze(nes, snes)['passed'])
            video[(0x2000+CURSORS[1])*2] = 187
            (snes/f'{phase}.vram').write_bytes(video)

            pixels = Image.open(snes/f'{phase}.png').convert('RGB')
            pixels.putpixel((REGION[0]+3, REGION[1]+3), (0, 0, 0))
            pixels.save(snes/f'{phase}.png')
            self.assertFalse(_analyze(nes, snes)['passed'])
            self.assertIn(CURSORS[0], OFFSETS)


if __name__ == '__main__':
    unittest.main()
