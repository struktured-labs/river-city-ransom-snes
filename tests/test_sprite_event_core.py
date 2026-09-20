import unittest
from tools.build_sprite_event_core import transform


class SpriteEventCoreTests(unittest.TestCase):
    def test_exact_hooks_and_reject_duplicate_or_changed_sites(self):
        samples = {'gfx.cpp': '#include "../../tools/snes9x_background.inc"\n\t\tRenderScreen(FALSE);',
                   'dma.cpp': 'bool8 S9xDoDMA (uint8 Channel)\n{',
                   'cpuexec.cpp': '\t\t#include "../../tools/snes9x_cpu_profile.inc"'}
        for name, text in samples.items():
            result = transform(name, text)
            self.assertIn('snes9x_sprite_', result)
            for broken in ('', text+text, result):
                with self.assertRaises(ValueError): transform(name, broken)
        self.assertLess(transform('gfx.cpp', samples['gfx.cpp']).index("rcr_sprite_event('R'"),
                        transform('gfx.cpp', samples['gfx.cpp']).index('RenderScreen(FALSE)'))
