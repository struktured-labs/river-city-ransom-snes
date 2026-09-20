import unittest

from tools.shop_qol import ConsumptionHistory, STATS, stat_delta


class ShopQolTests(unittest.TestCase):
    def stats(self, **changes):
        return dict(dict.fromkeys(STATS, 15), **changes)

    def test_repeat_combat_gains_are_not_exhausted(self):
        h = ConsumptionHistory()
        first = h.consumed(0, 94, self.stats(), self.stats(agility=16, strength=16))
        second = h.consumed(0, 94, self.stats(agility=16, strength=16),
                            self.stats(agility=17, strength=17))
        self.assertTrue(first['first_consumption'])
        self.assertFalse(second['first_consumption'])
        self.assertEqual(second['actual_delta']['combat'], {'agility': 1, 'strength': 1})
        self.assertFalse(second['marker']['bonus_exhausted'])

    def test_player_history_is_independent(self):
        h = ConsumptionHistory()
        h.consumed(0, 94, self.stats(), self.stats())
        self.assertEqual(h.describe(0, 94)['marker'], 'TRIED')
        self.assertEqual(h.describe(1, 94)['marker'], 'NEW')

    def test_browsing_or_cancelling_does_not_record_consumption(self):
        h = ConsumptionHistory()
        for _ in range(4):
            self.assertFalse(h.describe(0, 94)['previously_consumed'])
        self.assertEqual(h.seen, [set(), set()])

    def test_cap_and_recovery_are_separate(self):
        h = ConsumptionHistory()
        before = self.stats(agility=63, stamina=31, max_power=63)
        after = self.stats(agility=63, stamina=63, max_power=71)
        result = h.consumed(0, 94, before, after)
        self.assertEqual(result['actual_delta']['combat'], {})
        self.assertEqual(result['actual_delta']['stamina'], 32)
        self.assertEqual(result['actual_delta']['max_power'], 8)
        self.assertFalse(result['marker']['bonus_exhausted'])

    def test_invalid_and_partial_data_fail_closed(self):
        h = ConsumptionHistory()
        for player, item in ((2, 94), (0, 0), (0, 128), (False, 2)):
            with self.assertRaises(ValueError): h.describe(player, item)
        with self.assertRaises(ValueError): stat_delta({'agility': 15}, {'agility': 16})
        with self.assertRaises(ValueError): h.consumed(0, 94, self.stats(), self.stats(agility=256))
        self.assertEqual(h.seen, [set(), set()])


if __name__ == '__main__': unittest.main()
