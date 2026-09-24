import unittest
from pathlib import Path

from tools.build_difficulty_modes import SLOT, SIZE, snes_unique
from tools.nes_difficulty import planned_skill_levels

PARENT = Path('build/chromatic-wub-game-4146/native-cpu.sfc')


class DifficultyPatchLayoutTests(unittest.TestCase):
    def parent_bytes(self):
        if not PARENT.is_file():
            self.skipTest('4146 not built')
        return PARENT.read_bytes()

    def test_helper_slot_is_free_on_4146(self):
        data = self.parent_bytes()
        for bank in range(1, 9):
            at = bank * 65536 + SLOT
            self.assertEqual(data[at:at + SIZE], b'\xff' * SIZE)

    def test_b900_preimage_still_original(self):
        data = self.parent_bytes()
        self.assertEqual(data[snes_unique(0x13900):snes_unique(0x13900) + 3], bytes.fromhex('8c3400'))

    def test_menu_cmp_2_still_original(self):
        data = self.parent_bytes()
        self.assertEqual(data[snes_unique(0x17b44) + 3:snes_unique(0x17b44) + 5], bytes.fromhex('c902'))

    def test_built_4162_keeps_original_add_table(self):
        rom = Path('build/difficulty-modes-4162/native-cpu.sfc')
        if not rom.exists():
            self.skipTest('4162 not built')
        data = rom.read_bytes()
        self.assertEqual(data[snes_unique(0x13946):snes_unique(0x13946) + 4], bytes.fromhex('f0001020'))
        self.assertEqual(data[snes_unique(0x13900)], 0x4c)

    def test_planned_ram_does_not_steal_novice_or_advanced(self):
        by_name = {row['name']: row for row in planned_skill_levels()}
        self.assertEqual(by_name['Novice']['ram'], 1)
        self.assertEqual(by_name['Advanced']['ram'], 2)
        self.assertEqual(by_name['Gamer Mode']['ram'], 3)
        self.assertEqual(by_name['Intermediate']['ram'], 4)
        self.assertEqual(len({row['ram'] for row in by_name.values()}), 4)
