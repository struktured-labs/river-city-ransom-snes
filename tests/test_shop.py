import unittest
import numpy as np
from PIL import Image
from tools.check_shop import menu_pixels, REGION


class ShopPixelsTests(unittest.TestCase):
    def test_fixed_region_includes_boundary_and_last_pixel(self):
        pixels = np.zeros((240, 256, 3), dtype=np.uint8)
        x0, y0, x1, y1 = REGION
        pixels[y0, x0] = 255
        pixels[y1-1, x1-1] = 248
        pixels[y0-1, x0] = 255
        result = menu_pixels(Image.fromarray(pixels))
        self.assertEqual(result.shape, (110, 158, 3))
        self.assertEqual(np.count_nonzero(result), 6)
        self.assertTrue(np.all(result[0, 0] == 31))
        self.assertTrue(np.all(result[-1, -1] == 31))

    def test_low_bits_only_are_discarded(self):
        a = Image.new('RGB', (256, 240), (248, 16, 8))
        b = Image.new('RGB', (256, 239), (255, 23, 15))
        np.testing.assert_array_equal(menu_pixels(a), menu_pixels(b))
        b.putpixel((100, 100), (247, 23, 15))
        self.assertFalse(np.array_equal(menu_pixels(a), menu_pixels(b)))
