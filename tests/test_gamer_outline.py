import unittest

from tools.build_gamer_outline import (GOON_BIT, is_enemy, marked_attr, nes_attr_map,
                                       outline_colors, sprite_palette)

# Street sprite palettes: color 1 is the black outline, color 2 is the shirt.
STREET = (
    (0x0F, 0x0F, 0x30, 0x26),
    (0x0F, 0x0F, 0x11, 0x26),
    (0x0F, 0x0F, 0x20, 0x10),
    (0x0F, 0x0F, 0x2C, 0x26),
)
# Room gang table at $B5E8: every gang class the game spawns.
GANGS = (0x02, 0x08, 0x04, 0x05, 0x06, 0x01, 0x07, 0x00, 0x03)
BOSSES = range(0x09, 0x19)
TOWNSFOLK = (0x19, 0x1A, 0x1C, 0x1D, 0x20, 0x21, 0x22, 0x25)
# Sprite kinds: bank 9 $B95B gives gangs kind 2 and the big bosses 3-7; room
# objects (sticks, chains, boxes, cans, money) are $08-$11.
FIGHTER_KINDS = (2, 3, 4, 5, 6, 7)
OBJECT_KINDS = range(0x08, 0x12)


class GamerOutlineTests(unittest.TestCase):
    def test_each_palette_keeps_its_shirt_and_only_recolors_the_outline(self):
        copied = [tuple(outline_colors(pal)) for pal in STREET]
        self.assertEqual(copied[0], (0x0F, 0x16, 0x30, 0x26))
        self.assertEqual(copied[1], (0x0F, 0x16, 0x11, 0x26))
        self.assertTrue(all(pal[1] == 0x16 and pal[2] == src[2] and pal[3] == src[3]
                            for pal, src in zip(copied, STREET)))

    def test_every_gang_and_boss_in_an_enemy_slot_moves_to_the_red_copy(self):
        for cls in (*GANGS, *BOSSES):
            for slot in (2, 3, 7):
                for pal in range(4):
                    self.assertEqual(sprite_palette(pal, slot, cls, 3), pal + 4)

    def test_players_are_never_marked_even_with_a_gang_class(self):
        # Alex and Ryan are class 0, which is also a gang number.
        for slot in (0, 1):
            for cls in (0, 2, 8):
                self.assertFalse(is_enemy(slot, cls))
                self.assertEqual(sprite_palette(1, slot, cls, 3), 1)

    def test_townsfolk_and_shops_are_never_marked(self):
        for cls in TOWNSFOLK:
            for slot in (2, 3, 8, 9):
                self.assertEqual(sprite_palette(2, slot, cls, 3), 2)
        for slot in (8, 9, 10):
            self.assertEqual(sprite_palette(0, slot, 2, 3), 0)
        self.assertEqual(sprite_palette(0, 2, 2, 3, shop=1), 0)

    def test_flips_and_priority_survive_the_goon_bit(self):
        for attr in (0x00, 0x21, 0x42, 0x83, 0xE3):
            plain = nes_attr_map()[attr]
            red = nes_attr_map()[marked_attr(attr, 2, 2, 3)]
            self.assertEqual(red, plain | 0x08)

    def test_other_skills_never_mark(self):
        for skill in (1, 2, 4):
            self.assertEqual(marked_attr(0x01, 2, 2, skill), 0x01)

    def test_unmarked_map_is_the_parent_map(self):
        for a in range(256):
            if not a & GOON_BIT:
                self.assertEqual(nes_attr_map()[a], nes_attr_map(False)[a])

    def test_weapons_and_objects_in_enemy_slots_are_never_marked(self):
        # Objects share slots 2-7 with gang members and keep a stale class.
        for kind in OBJECT_KINDS:
            for cls in (*GANGS, 0x0C):
                for slot in (2, 5, 7):
                    self.assertEqual(sprite_palette(1, slot, cls, 3, kind=kind), 1)

    def test_a_held_weapon_drawn_by_its_goon_is_not_marked(self):
        for kind in FIGHTER_KINDS:
            self.assertEqual(sprite_palette(2, 3, 2, 3, kind=kind, part=0x80), 2)
            self.assertEqual(sprite_palette(2, 3, 2, 3, kind=kind, part=0), 6)
            # $FF sub-parts ($0012 = return index < $80) are still body
            self.assertEqual(sprite_palette(2, 3, 2, 3, kind=kind, part=0x05), 6)
