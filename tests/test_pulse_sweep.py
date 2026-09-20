import unittest
from tools.correct_pulse_sweep import correct
from tools.check_pulse_sweep import expected


class PulseSweepTests(unittest.TestCase):
    def engine(self):
        data=bytearray(0x2c00)
        data[0x60b:0x618]=bytes.fromhex('e47880a801c478e479a800c479')
        data[0x63f:0x64c]=bytes.fromhex('e47a80a478c47ae47ba479c47b')
        return bytes(data)

    def test_nes_target(self):
        self.assertEqual(expected(172,4,False),182)
        self.assertEqual(expected(172,4,True),161)
        self.assertEqual(expected(8,7,False),8)
        self.assertEqual(expected(8,7,True),7)

    def test_only_arithmetic_block_changes(self):
        before=self.engine();after=correct(before)
        self.assertEqual(len(before),len(after))
        self.assertTrue(all(i in range(0x60b,0x618) or i==0x641
                            for i,(a,b) in enumerate(zip(before,after)) if a!=b))
        self.assertEqual(after[0x60b:0x618],bytes(8)+bytes((0x2f,3))+bytes(3))
        self.assertEqual(after[0x641],0x60)

    def test_reject_changed_preimage(self):
        for offset in (0x60b,0x617,0x63f,0x641,0x64b):
            data=bytearray(self.engine());data[offset]^=1
            with self.assertRaises(ValueError):correct(bytes(data))

    def test_double_application_rejected(self):
        with self.assertRaises(ValueError):correct(correct(self.engine()))
