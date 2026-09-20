import unittest
from pathlib import Path
from tools.analyze_spc_receive import compare
from tools.prepare_audio import paired_engine


class PairedTransferTests(unittest.TestCase):
    def test_triangle_control_preserves_paired_receiver(self):
        source = (Path(__file__).resolve().parents[1] / '.deps/upernes/source/asm/Memblers_2a03.bin').read_bytes()
        good = paired_engine(source)
        control = paired_engine(source, triangle_fix=False)
        self.assertEqual(len(good), 0x2C1F)
        self.assertEqual([i for i, (a, b) in enumerate(zip(good, control)) if a != b], [0x28e])
        self.assertEqual(control[0x28e], 0xF3)

    def streams(self):
        sent = [['P', '1', '10', '0', '1', str(i), str(i*7), '008000'] for i in range(23)]
        received = [[str(i), str(i*7), '3011' if i & 1 else '3008'] for i in range(23)]
        return sent, received

    def test_complete_pair_stream_and_single_tail(self):
        sent, received = self.streams()
        self.assertTrue(compare(sent, received, paired=True)['passed'])
        with self.assertRaises(ValueError):
            compare(sent, received)

    def test_wrong_second_byte_detected(self):
        sent, received = self.streams()
        received[1][1] = received[0][1]
        self.assertEqual(compare(sent, received, paired=True)['mismatch_count'], 1)

    def test_missing_tail_or_wrong_receive_site_rejected(self):
        sent, received = self.streams()
        with self.assertRaises(ValueError):
            compare(sent, received[:-1], paired=True)
        received[-1][2] = '3011'
        with self.assertRaises(ValueError):
            compare(sent, received, paired=True)
