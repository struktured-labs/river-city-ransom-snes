import unittest
from tools.analyze_spc_receive import compare, length_usage


class ReceiverTests(unittest.TestCase):
    def test_triple_checks_every_port_and_zero_padding(self):
        sent, received = self.streams()
        received.append(['23', '0', '3010'])
        for i,row in enumerate(received):
            row[2] = f'{0x3008+4*(i%3):04x}'
        result = compare(sent, received, triple=True)
        self.assertTrue(result['passed'])
        self.assertEqual(result['physical_stores'],24)
        for index in (0,1,2):
            bad = [r.copy() for r in received]
            bad[index][1] = '99'
            self.assertFalse(compare(sent,bad,triple=True)['passed'])
        for bad in (received[:-1], received[:2]+received[3:]):
            with self.assertRaises(ValueError):
                compare(sent,bad,triple=True)
        received[-1][1] = '1'
        with self.assertRaisesRegex(ValueError,'padding'):
            compare(sent,received,triple=True)

    def test_length_halt_masks_and_disabled_channels(self):
        p = bytearray(23)
        p[21] = 15
        p[0] = p[4] = p[12] = 32
        p[8] = 128
        self.assertFalse(length_usage([p])['enabled_running_events'])
        p[8] = 32          # triangle uses bit 7, not the pulse/noise bit 5
        r = length_usage([p])
        self.assertEqual([e['channel'] for e in r['enabled_running_events']], [2])
        p[21] = 0
        self.assertFalse(length_usage([p])['enabled_running_events'])
        self.assertTrue(all(c['disabled'] == 1 for c in length_usage([p])['channels']))

    def streams(self):
        sent = [['P', '1', '0', '0', '1', str(i), str(i + 10), 'c08000'] for i in range(23)]
        received = [[str(i), str(i + 10), '048f'] for i in range(23)]
        return sent, received

    def test_exact_and_stale_data(self):
        a, b = self.streams()
        self.assertTrue(compare(a, b)['passed'])
        b[7][1] = b[6][1]
        result = compare(a, b)
        self.assertFalse(result['passed'])
        self.assertEqual(result['mismatch_count'], 1)
        self.assertEqual(result['mismatches'][0]['index'], 7)

    def test_reject_incomplete_or_wrong_receiver(self):
        a, b = self.streams()
        for received in ([], b[:-1], b + b[:1]):
            with self.assertRaises(ValueError):
                compare(a, received)
        b[0][2] = '0490'
        with self.assertRaises(ValueError):
            compare(a, b)

    def test_reject_reordered_or_invalid_values(self):
        for target in (0, 1):
            for field, value in ((0, '1'), (1, '256')):
                a, b = self.streams()
                (a if target == 0 else b)[0][field + (5 if target == 0 else 0)] = value
                with self.assertRaises(ValueError):
                    compare(a, b)
