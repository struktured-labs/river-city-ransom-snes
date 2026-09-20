import unittest
from tools.analyze_game_keyons import analyze


class GameKeyonTests(unittest.TestCase):
    def test_ident_startup_requires_exact_prefix_and_explicit_model(self):
        prefix = ['K', '0', '3', '033b']
        rows = [prefix, *self.rows()]
        self.assertTrue(analyze(rows, splash_ident=True)['passed'])
        with self.assertRaises(ValueError):
            analyze(rows)
        for broken in (self.rows(), [prefix, *rows],
                       [['K', '0', '1', '033b'], *self.rows()],
                       [['K', '0', '3', '033c'], *self.rows()],
                       [*self.rows(), prefix]):
            with self.assertRaises(ValueError):
                analyze(broken, splash_ident=True)

    def rows(self):
        return [
            ['K','0','0','0bcb'], ['K','0','15','0456'],
            ['P','1','0','0','0','0','3008'],
            ['P','2','1','3','64','0','3008'], ['K','2','1','3035'],
            ['P','3','2','3','64','128','3008'], ['K','3','2','3035'],
            ['P','4','3','3','128','192','3008'], ['K','4','3','3035'],
            ['P','5','0','0','0','0','3008'],
            ['P','6','0','3','128','192','3008'],
        ]

    def test_reset_duty_and_both_voice_schedule(self):
        result = analyze(self.rows())
        self.assertTrue(result['passed'])
        self.assertEqual(result['expected_keyon_writes'], 3)
        self.assertEqual(result['merged_reset_duty_packets'], 3)
        self.assertEqual(result['both_voice_packets'], 1)

    def test_missing_duplicate_and_lost_voice_detected(self):
        for mutate in (
            lambda r: r.remove(['K','2','1','3035']),
            lambda r: r.insert(r.index(['K','2','1','3035']), ['K','2','1','3035']),
            lambda r: r.__setitem__(r.index(['K','4','3','3035']), ['K','4','1','3035'])):
            rows = self.rows()
            mutate(rows)
            self.assertFalse(analyze(rows)['passed'])

    def test_disabled_duty_does_not_advance_engine_state(self):
        rows = self.rows()
        # Packet 6 re-enables voices after disabled controls changed to zero;
        # old enabled duty state remains [2,3], so no key-on is expected.
        self.assertTrue(analyze(rows)['passed'])

    def test_wrong_site_order_and_startup_rejected(self):
        for rows in (
            self.rows()[1:],
            self.rows()+[['K','4','3','3035']],
            [*self.rows()[:-1], ['P','7','0','3','0','0','3008']]):
            with self.assertRaises(ValueError):
                analyze(rows)

    def test_triple_fast_combines_reset_and_preserves_duty_only_sites(self):
        rows = [
            ['K','0','0','0bcb'], ['K','0','15','0456'],
            ['P','1','0','3','0','0','300c'],
            ['P','2','0','3','64','128','300c'],
            ['K','2','1','3072'], ['K','2','2','307d'],
            ['P','3','3','3','128','192','300c'], ['K','3','3','3062'],
        ]
        result = analyze(rows, triple=True, fast=True)
        self.assertTrue(result['passed'])
        self.assertEqual(result['expected_keyon_writes'], 3)
        self.assertEqual(result['transport'], 'triple')
        self.assertEqual(result['schedule'], 'fast')
