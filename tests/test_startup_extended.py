import unittest
from tools.review_startup_game_extended import sprite_cache_cases


class StartupExtendedTests(unittest.TestCase):
    def test_cache_correspondence_does_not_waive_either_direction(self):
        a = [dict(frame=1, prepared_oam='a', nes_oam_shadow='s', cached_oam_source='s'),
             dict(frame=2, prepared_oam='b', nes_oam_shadow='s', cached_oam_source='old')]
        b = [dict(frame=1, prepared_oam='c', nes_oam_shadow='s', cached_oam_source='old'),
             dict(frame=2, prepared_oam='d', nes_oam_shadow='s', cached_oam_source='s')]
        r = sprite_cache_cases(a, b)
        self.assertEqual(len(r['cases']), 2)
        self.assertEqual(len(r['populations']), 2)
        self.assertEqual(sum(x['frames'] for x in r['populations']), 2)
        with self.assertRaises(ValueError):
            sprite_cache_cases(a, b[:1])
        with self.assertRaises(ValueError):
            sprite_cache_cases(a, b[::-1])
