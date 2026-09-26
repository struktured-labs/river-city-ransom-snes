import unittest

from tools.build_gamer_outline import outline_colors, sprite_palette

# Street sprite palettes: color 1 is the black outline, color 2 is the shirt.
STREET = (
    (0x0F, 0x0F, 0x30, 0x26),
    (0x0F, 0x0F, 0x11, 0x26),
    (0x0F, 0x0F, 0x20, 0x10),
    (0x0F, 0x0F, 0x2C, 0x26),
)


class GamerOutlineTests(unittest.TestCase):
    def test_each_palette_keeps_its_shirt_and_only_recolors_the_outline(self):
        copied = [tuple(outline_colors(pal)) for pal in STREET]
        self.assertEqual(copied[0], (0x0F, 0x16, 0x30, 0x26))
        self.assertEqual(copied[1], (0x0F, 0x16, 0x11, 0x26))
        self.assertEqual(copied[2][2], 0x20)
        self.assertEqual(copied[3][2], 0x2C)
        self.assertTrue(all(pal[1] == 0x16 and pal[2] == src[2] and pal[3] == src[3]
                            for pal, src in zip(copied, STREET)))

    def test_player_sprites_stay_on_the_original_palette(self):
        self.assertEqual(sprite_palette(0, 116, 128, (116, 83), 3, (40,)), 0)
        self.assertEqual(sprite_palette(1, 124, 140, (116, 83), 3, (40,)), 1)
        self.assertEqual(sprite_palette(0, 108, 121, (116, 83), 3, (40,)), 0)
        # Alex is wider than 16px. The working bubble was 28.
        self.assertEqual(sprite_palette(0, 96, 128, (116,), 3, (40,)), 0)

    def test_other_sprites_use_the_red_outline_copy(self):
        # A bystander, even on palette 0, is not recolored.
        self.assertEqual(sprite_palette(0, 10, 128, (116, 83), 3), 0)
        # The goon keeps his own shirt palette and moves to the red-outline copy.
        self.assertEqual(sprite_palette(0, 48, 128, (116, 83), 3, (40,)), 4)
        self.assertEqual(sprite_palette(1, 48, 140, (116, 83), 3, (40,)), 5)
        self.assertEqual(sprite_palette(2, 48, 130, (116,), 3, (40,)), 6)
        self.assertEqual(sprite_palette(0, 80, 130, (116,), 3, (200,)), 0)

    def test_leaving_gamer_and_hidden_sprites_are_not_retinted(self):
        self.assertEqual(sprite_palette(0, 40, 128, (116, 83), 1), 0)
        self.assertEqual(sprite_palette(1, 40, 0xF0, (116, 83), 3), 1)
