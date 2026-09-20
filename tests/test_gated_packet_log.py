import unittest

from tools.audit_gated_packet_log import calls, qualify


class GatedPacketLogTests(unittest.TestCase):
    def test_global_packet_index_is_not_record_sequence(self):
        entries = [dict(packet=i, nmi=(65534 + i) % 65536, frame=i, clock=i, recorded=i in (1, 3)) for i in range(4)]
        packets = [bytes([i]) * 23 for i in range(4)]
        log = dict(total=2, overwritten=0, records=[dict(sequence=j, nmi=entries[i]['nmi'],
            timeout=False, packet=packets[i].hex()) for j, i in enumerate((1, 3))])
        r = qualify(log, entries, packets)
        self.assertEqual(r['deliberately_unrecorded'], 2)
        self.assertEqual(len(r['ranges']), 4)
        log['records'][0]['nmi'] ^= 1
        with self.assertRaises(ValueError):
            qualify(log, entries, packets)

    def test_incomplete_or_wrong_gate_events_fail(self):
        first = ['0','1','20','0','100','c0e600'] + ['1'] * 10
        second = ['1','1','20','20','120','c0e080'] + ['1'] * 10
        self.assertEqual(calls([first, second])[0]['recorded'], True)
        with self.assertRaises(ValueError):
            calls([first])
        second[5] = 'c0d2bc'
        with self.assertRaises(ValueError):
            calls([first, second])
