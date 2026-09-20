import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from tools.audit_scroll_publication import game_state, mismatch, select_frames, stable_target


def row(frame, camera, published, room=2):
    ram = bytearray(2048)
    ram[0xDC:0xDE] = camera.to_bytes(2, 'little')
    ram[0x42] = room
    ram[0xF6] = camera & 255
    ram[0x3D] = (camera >> 8) & 1
    return {'frame': frame, 'game_ram_hex': ram.hex(),
            'native': {'logical_camera_x': camera,
                       'hdma_street_scroll_x': published}}


class ScrollPublicationTests(unittest.TestCase):
    def test_first_and_settled_frames_are_not_conflated(self):
        reference = [row(10, 110, 110)]
        candidate = [row(20, 110, 109), row(21, 110, 110)]
        ref, first, settled = select_frames(reference, candidate, 110, 2)
        self.assertEqual((ref['frame'], first['frame'], settled['frame']), (10, 20, 21))

    def test_missing_publication_fails_closed(self):
        with self.assertRaises(ValueError):
            select_frames([row(1, 5, 5)], [row(2, 5, 4)], 5, 2)

    def test_stable_target_is_second_consecutive_sample_not_image_selected(self):
        rows = [row(1, 5, 4), row(2, 6, 5), row(3, 5, 5), row(4, 5, 5)]
        self.assertEqual(stable_target(rows, 5, 2)['frame'], 4)
        with self.assertRaises(ValueError):
            stable_target(rows[:3], 5, 2)

    def test_rgb555_ignores_only_subquantum_palette_rounding(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b, c = (Path(tmp)/name for name in ('a.png', 'b.png', 'c.png'))
            base = np.zeros((224, 256, 3), dtype=np.uint8)
            Image.fromarray(base).save(a)
            rounded = base.copy(); rounded[32, 0] = 6
            Image.fromarray(rounded).save(b)
            changed = base.copy(); changed[32, 0] = 8
            Image.fromarray(changed).save(c)
            self.assertEqual(mismatch(a, b)[0], 0)
            self.assertEqual(mismatch(a, c)[0], 1)

    def test_game_state_requires_full_original_ram(self):
        with self.assertRaises(ValueError):
            game_state({'game_ram_hex': '00'})


if __name__ == '__main__':
    unittest.main()
