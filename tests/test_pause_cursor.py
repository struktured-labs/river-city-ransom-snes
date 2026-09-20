import tempfile
import unittest
from pathlib import Path

from PIL import Image

from tools.benchmark_capture import scenario_for
from tools.check_pause_cursor import HELP_CURSOR, PHASES, REGION, _analyze


class PauseCursorTests(unittest.TestCase):
    def test_replay_exits_then_reopens_with_released_inputs(self):
        phases = scenario_for('pause-cursor-return')
        names = [phase['name'] for phase in phases]
        self.assertLess(names.index('pause_right_visible_4'), names.index('pause_cancel'))
        self.assertLess(names.index('pause_cancel'), names.index('pause_close'))
        self.assertEqual(phases[names.index('pause_reopen')]['buttons'], ['Start'])
        self.assertNotIn('buttons', phases[-1])

    def test_rejects_lingering_shadow_vram_or_pixels(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            nes, snes = root/'nes', root/'snes'
            nes.mkdir()
            snes.mkdir()
            for phase in PHASES:
                help_selected = phase in ('pause_right_visible_4', 'pause_cancel_visible')
                for folder in (nes, snes):
                    table = bytearray(2048)
                    video = bytearray(65536)
                    frame = Image.new('RGB', (256, 240 if folder == nes else 239))
                    if help_selected:
                        table[HELP_CURSOR] = 187
                        video[(0x2000+HELP_CURSOR)*2] = 187
                        frame.putpixel((REGION[0]+3, REGION[1]+3), (248, 248, 248))
                    (folder/f'{phase}.nametable').write_bytes(table)
                    (folder/f'{phase}.vram').write_bytes(video)
                    frame.save(folder/f'{phase}.png')
            self.assertTrue(_analyze(nes, snes)['passed'])
            phase = 'pause_reopen_visible'
            shadow = bytearray((snes/f'{phase}.nametable').read_bytes())
            shadow[HELP_CURSOR] = 187
            (snes/f'{phase}.nametable').write_bytes(shadow)
            self.assertFalse(_analyze(nes, snes)['passed'])
            shadow[HELP_CURSOR] = 0
            (snes/f'{phase}.nametable').write_bytes(shadow)

            video = bytearray((snes/f'{phase}.vram').read_bytes())
            video[(0x2000+HELP_CURSOR)*2] = 187
            (snes/f'{phase}.vram').write_bytes(video)
            self.assertFalse(_analyze(nes, snes)['passed'])
            video[(0x2000+HELP_CURSOR)*2] = 0
            (snes/f'{phase}.vram').write_bytes(video)

            image = Image.open(snes/f'{phase}.png').convert('RGB')
            image.putpixel((REGION[0]+3, REGION[1]+3), (248, 248, 248))
            image.save(snes/f'{phase}.png')
            self.assertFalse(_analyze(nes, snes)['passed'])


if __name__ == '__main__':
    unittest.main()
