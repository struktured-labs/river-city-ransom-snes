import unittest

from tools.build_gamer_outline import (GOON_BIT, HELD_PART, RED_NES, SHADOW_STORES, is_enemy, marked_attr,
                                       nes_attr_map, outline_colors, outline_tile,
                                       sprite_actor, sprite_palette, tile_pixels)

# Street sprite palettes: color 1 is the black outline, color 2 is the shirt
# or jeans, color 3 is skin.
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


def tile_from(rows):
    """Zero-extended 4bpp tile from 8 strings of color digits 0-3."""
    t = bytearray(32)
    for r, row in enumerate(rows):
        for c, ch in enumerate(row):
            v = int(ch)
            t[2 * r] |= (v & 1) << (7 - c)
            t[2 * r + 1] |= (v >> 1 & 1) << (7 - c)
    return bytes(t)


def actor_palette(nes_pal, drawer, held, actors, skill=3):
    """sprite_palette for a sprite written by slot `drawer`, optionally inside
    a held-object part naming `held`. actors: slot -> (class, kind)."""
    part = HELD_PART if held is not None else 0
    who = sprite_actor(drawer, part, held)
    cls, kind = actors[who]
    return sprite_palette(nes_pal, who, cls, skill, kind=kind, part=part)


class GamerOutlineTests(unittest.TestCase):
    def test_normal_palettes_repeat_the_outline_and_red_copies_only_color5(self):
        for src in STREET:
            normal, red = outline_colors(src)
            self.assertEqual(normal[:4], list(src))
            self.assertEqual(normal[5], src[1])
            self.assertEqual(red[:4], list(src))
            self.assertEqual(red[5], RED_NES)
            self.assertEqual(red[1], src[1])      # the rest of the outline stays dark

    def test_every_gang_and_boss_moves_body_palettes_to_the_red_copy(self):
        for cls in (*GANGS, *BOSSES):
            for slot in (2, 3, 7):
                for pal in (0, 1, 3):
                    self.assertEqual(sprite_palette(pal, slot, cls, 3), pal + 4)
                # palette 2 is items: never red
                self.assertEqual(sprite_palette(2, slot, cls, 3), 2)

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
            self.assertEqual(sprite_palette(1, slot, 2, 3), 1)
        self.assertEqual(sprite_palette(1, 2, 2, 3, shop=1), 1)

    def test_flips_and_priority_survive_the_goon_bit(self):
        for attr in (0x01, 0x21, 0x42, 0x83, 0xE3, 0x00, 0xC0):
            plain = nes_attr_map()[attr]
            red = nes_attr_map()[marked_attr(attr, 2, 2, 3)]
            self.assertEqual(red, plain | 0x08 if attr & 3 != 2 else plain)

    def test_shadow_hooks_cover_color1_of_every_sprite_palette(self):
        # The unrolled pending_palette stores are sta f:$7E5502+32p (color 1).
        stores = sorted(old for old, _ in SHADOW_STORES.values() if old.startswith('8f'))
        self.assertEqual(stores, [f'8f{0x02 + 32 * p:02x}557e' for p in range(4)])
        self.assertIn(('9f00557e', 'sh_idx'), SHADOW_STORES.values())
        # One DMA from the 32-byte-stride shadow reaches color 5 of palette 3.
        self.assertEqual(0x6C, 3 * 32 + 6 * 2)

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

    def test_held_parts_are_judged_by_the_held_actor(self):
        for kind in FIGHTER_KINDS:
            actors = {0: (0, 0), 1: (0, 0), 3: (2, kind), 6: (2, 0x0A), 2: (4, kind)}
            # a goon's own body, and its $FF sub-parts, stay red
            self.assertEqual(actor_palette(3, 3, None, actors), 7)
            # a weapon a goon holds (kind $0A in slot 6) is not red
            self.assertEqual(actor_palette(3, 3, 6, actors), 3)
            # Alex carrying a knocked-down goon: the goon stays red
            self.assertEqual(actor_palette(3, 0, 3, actors), 7)
            self.assertEqual(actor_palette(1, 1, 2, actors), 5)
            # a goon grabbing Alex: Alex is not red
            self.assertEqual(actor_palette(1, 3, 0, actors), 1)
            # Alex carrying a weapon: not red
            self.assertEqual(actor_palette(3, 0, 6, actors), 3)

    def test_only_the_outer_silhouette_is_recolored(self):
        tile = tile_from([
            "00000000",
            "00111100",
            "01222210",
            "01212210",
            "01333310",
            "01311310",
            "00111100",
            "00000000",
        ])
        px = tile_pixels(outline_tile(tile))
        base = tile_pixels(tile)
        # every outline pixel with a transparent neighbour becomes 5
        for r, c in ((1, 2), (1, 3), (1, 4), (1, 5), (2, 1), (2, 6), (3, 1), (3, 6), (4, 1),
                     (4, 6), (5, 1), (5, 6), (6, 2), (6, 3), (6, 4), (6, 5)):
            self.assertEqual(px[r][c], 5, (r, c))
        # interior dark pixels (a line in the shirt, a mouth in the skin) stay 1
        for r, c in ((3, 3), (5, 3), (5, 4)):
            self.assertEqual(px[r][c], 1, (r, c))
        # nothing but 1 -> 5 changes; skin and clothes are untouched
        for r in range(8):
            for c in range(8):
                if px[r][c] != base[r][c]:
                    self.assertEqual((base[r][c], px[r][c]), (1, 5))

    def test_tile_edge_is_not_outer(self):
        tile = tile_from(["12222222"] + ["22222222"] * 7)
        self.assertEqual(tile_pixels(outline_tile(tile))[0][0], 1)

    def test_diagonal_contact_is_not_a_neighbour(self):
        tile = tile_from(["12000000", "20000000"] + ["00000000"] * 6)
        # the only transparent pixel near (0,0) is diagonal
        self.assertEqual(tile_pixels(outline_tile(tile))[0][0], 1)

    def test_recolor_needs_a_zero_extended_tile(self):
        with self.assertRaises(ValueError):
            outline_tile(bytes(16) + b'\x01' + bytes(15))
