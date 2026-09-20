import unittest
import numpy as np
from tools.build_cursor_audio_review import cursor, CURSOR_BOXES


class CursorReviewTests(unittest.TestCase):
    def image(self, slots):
        image = np.zeros((1080,1920,3),dtype=np.uint8)
        for slot in slots:
            x,y,r,b = CURSOR_BOXES[slot]
            image[y:b,x:r] = 255
        return image

    def test_each_slot(self):
        for slot in range(5):
            self.assertEqual(cursor(self.image([slot]))['index'],slot)

    def test_missing_cursor(self):
        with self.assertRaises(ValueError):
            cursor(self.image([]))

    def test_duplicate_cursor(self):
        with self.assertRaises(ValueError):
            cursor(self.image([0,1]))

    def test_partial_artifact(self):
        image = self.image([0]); image[900:903,1095:1100] = 255
        with self.assertRaises(ValueError):
            cursor(image)

    def test_wrong_geometry(self):
        with self.assertRaises(ValueError):
            cursor(np.zeros((240,256,3),dtype=np.uint8))
