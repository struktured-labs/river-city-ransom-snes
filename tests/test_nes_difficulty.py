import unittest
from pathlib import Path

from tools.nes_difficulty import (
    SIMON_CLASS, SKILL_ADVANCED, SKILL_NOVICE, apply_boss, class_stats,
    prg_from, simon_spawn, skill_add_table, wrap_hypothesis,
)

ROM = Path('roms/river-city-ransom-us.nes')


class NesDifficultyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prg = prg_from(ROM.read_bytes())

    def test_skill_add_table_has_four_slots(self):
        self.assertEqual(skill_add_table(self.prg), (-16, 0, 16, 32))

    def test_simon_class_matches_community_novice_numbers(self):
        base = class_stats(self.prg, SIMON_CLASS)
        self.assertEqual(base['stamina'], 118)
        self.assertEqual(base['will'], 63)
        self.assertEqual(base['punch'], 61)

    def test_novice_simon_is_the_table_row(self):
        spawn, base = simon_spawn(self.prg, SKILL_NOVICE)
        self.assertEqual(spawn, base)

    def test_advanced_simon_is_not_a_wrap_below_novice(self):
        novice, _ = simon_spawn(self.prg, SKILL_NOVICE)
        advanced, _ = simon_spawn(self.prg, SKILL_ADVANCED)
        wrapped = wrap_hypothesis(novice['stamina'])
        self.assertEqual(wrapped['masked7'], 108)
        self.assertGreaterEqual(advanced['stamina'], novice['stamina'])
        self.assertGreaterEqual(advanced['punch'], novice['punch'])
        self.assertEqual(advanced['will'], novice['will'])
        self.assertEqual(advanced['stamina'], 127)
        self.assertEqual(advanced['punch'], 63)
        self.assertNotEqual(advanced['stamina'], wrapped['masked7'])

    def test_boss_helper_saturates_instead_of_wrapping(self):
        self.assertEqual(apply_boss(118, SKILL_ADVANCED, stamina=True), 127)
        self.assertEqual(apply_boss(63, SKILL_ADVANCED), 63)
        self.assertEqual(apply_boss(1, 0), 1)

    def test_gamer_index_does_not_raise_simon_above_advanced_caps(self):
        advanced, _ = simon_spawn(self.prg, SKILL_ADVANCED)
        gamer, _ = simon_spawn(self.prg, 3)
        self.assertEqual(gamer['stamina'], advanced['stamina'])
        self.assertEqual(gamer['will'], advanced['will'])
        self.assertEqual(gamer['punch'], 63)

    def test_original_skill_ram_stays_one_and_two(self):
        from tools.nes_difficulty import planned_skill_levels
        by_name = {row['name']: row for row in planned_skill_levels()}
        self.assertEqual(by_name['Novice']['ram'], 1)
        self.assertEqual(by_name['Advanced']['ram'], 2)
        self.assertIsNone(by_name['Intermediate']['ram'])
        self.assertEqual(by_name['Intermediate']['add'], 8)
