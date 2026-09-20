import unittest

from tools.rcr_password import NES_LENGTH, SNES_LENGTH, classify, nes_fits


class PasswordKindTests(unittest.TestCase):
    def test_nes_guide_password_is_33(self):
        # Published River City High (end) password, spaces ignored.
        text = 'XfMdZTHwiR3 jaj6jfRUDEt tilm2tWRo8b'
        self.assertEqual(len(''.join(text.split())), NES_LENGTH)
        self.assertEqual(classify(text), 'nes')

    def test_snes_is_one_extra_row(self):
        nes = 'XfMdZTHwiR3jaj6jfRUDEttilm2tWRo8b'
        snes = nes + 'AAAAAAAAAAA'
        self.assertEqual(len(snes), SNES_LENGTH)
        self.assertEqual(classify(snes), 'snes')

    def test_wrong_length_is_invalid(self):
        self.assertEqual(classify('short'), 'invalid')
        self.assertEqual(classify('A' * 34), 'invalid')

    def test_gamer_or_overcap_cannot_use_nes_password(self):
        self.assertTrue(nes_fits(2, 63, 127))
        self.assertFalse(nes_fits(3, 63, 127))
        self.assertFalse(nes_fits(1, 80, 63))
        self.assertFalse(nes_fits(2, 63, 180))
