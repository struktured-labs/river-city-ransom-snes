import unittest
from pathlib import Path
from tools.build_cgram_read_core import transform


class CgramCoreTests(unittest.TestCase):
    def test_only_adds_two_memory_query_cases(self):
        source=Path('.deps/snes9x-voice-2292/libretro/libretro.cpp').read_text()
        result=transform(source)
        self.assertEqual(result.count('case 0x5243:'),2)
        self.assertIn('data = PPU.CGDATA;',result)
        self.assertIn('size = sizeof(PPU.CGDATA);',result)
        self.assertEqual(result[result.index('void retro_run'):result.index('void* retro_get_memory_data')],
                         source[source.index('void retro_run'):source.index('void* retro_get_memory_data')])

    def test_duplicate_or_changed_markers_rejected(self):
        with self.assertRaises(ValueError):transform('')
        source=Path('.deps/snes9x-voice-2292/libretro/libretro.cpp').read_text()
        with self.assertRaises(ValueError):transform(source+source)
