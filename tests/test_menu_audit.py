import unittest
import numpy as np
from tools.menu_audit import PHASES, evaluate


class MenuAuditTests(unittest.TestCase):
    def fixture(self):
        images = {s: {p: np.zeros((h, 256, 3), np.uint8) for p in PHASES}
                  for s, h in (('nes', 240), ('snes', 239))}
        for phases in images.values():
            for p in PHASES[1:]:
                phases[p][200, 20] = 255
            for p in PHASES[2:]:
                phases[p][10, 20] = 255
        return images

    def test_expected_transition(self):
        self.assertTrue(all(g['passed'] for g in evaluate(self.fixture())))

    def test_stale_hud_and_truncated_menu_fail(self):
        for phase, y in (('after_1_Select', 10), ('after_0_Start', 200)):
            images = self.fixture()
            images['snes'][phase][y, 20] = 0
            self.assertFalse(all(g['passed'] for g in evaluate(images)))

    def test_identical_blank_captures_cannot_pass(self):
        images = self.fixture()
        for phases in images.values():
            for frame in phases.values():
                frame[:] = 0
        self.assertFalse(all(g['passed'] for g in evaluate(images)))
