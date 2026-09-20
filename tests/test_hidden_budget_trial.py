import unittest

from tools.build_hidden_budget_trial import patch


class HiddenBudgetTrialTests(unittest.TestCase):
    def image(self):
        data = bytearray(131072)
        data[0x885d:0x8866] = bytes.fromhex('ada01cc902d004a910')
        return data

    def test_only_immediate_and_checksum(self):
        original = self.image()
        result, at = patch(original,0x8800,0x8900,16,8)
        self.assertEqual(at,0x8865)
        self.assertEqual(result[at],8)
        self.assertTrue(all(i == at or 0xffdc <= i < 0xffe0
            for i,(a,b) in enumerate(zip(original,result)) if a != b))
        self.assertEqual(sum(result)&65535,int.from_bytes(result[0xffde:0xffe0],'little'))

    def test_missing_guard_rejected(self):
        data = self.image()
        data[0x8861] = 0
        with self.assertRaises(ValueError):
            patch(data,0x8800,0x8900,16,8)

    def test_invalid_budget_and_ambiguous_preimage(self):
        for budget in (0,17,True):
            with self.subTest(budget=budget), self.assertRaises(ValueError):
                patch(self.image(),0x8800,0x8900,16,budget)
        data = self.image()
        data[0x8880:0x8889] = data[0x885d:0x8866]
        with self.assertRaises(ValueError):
            patch(data,0x8800,0x8900,16,8)
