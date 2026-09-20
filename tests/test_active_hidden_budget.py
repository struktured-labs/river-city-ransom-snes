import unittest

from tools.build_active_hidden_budget_trial import patch


class ActiveHiddenBudgetTests(unittest.TestCase):
    def fixture(self):
        rom=bytearray(2097152)
        rom[0x885d:0x886d]=bytes.fromhex('ada01cc902d004a9108002a9028d6b1c')
        rom[0xaa88:0xaa95]=b'\xff'*13
        return rom

    def test_only_branch_helper_checksum_change(self):
        before=self.fixture();after,meta=patch(before,0x8800,0xaa95,0xaa88,0xaa95)
        self.assertEqual(meta['resume'],0x886a)
        self.assertEqual(after[0x8864:0x8868],bytes.fromhex('4c88aaea'))
        allowed={*range(0x8864,0x8868),*range(0xaa88,0xaa94),*range(0xffdc,0xffe0)}
        self.assertTrue(all(i in allowed for i,(a,b) in enumerate(zip(before,after)) if a!=b))
        self.assertEqual(after[0xaa94],255)

    def test_occupied_padding_and_changed_branch_refused(self):
        for at in (0xaa88,0xaa94,0x8865):
            rom=self.fixture();rom[at]^=1
            with self.assertRaises(ValueError):patch(rom,0x8800,0xaa95,0xaa88,0xaa95)
