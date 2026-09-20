import unittest

from tools.audit_audio_packet_log import compare, received_packets, timing


class PacketLogAuditTests(unittest.TestCase):
    def test_receiver_order_and_incomplete_fail(self):
        rows = [[str(i), str(i), '32e5'] for i in range(23)]
        self.assertEqual(received_packets(rows), [bytes(range(23))])
        for broken in (rows[:-1], rows[1:], [], rows[:3] + rows[2:]):
            with self.assertRaises(ValueError):
                received_packets(broken)

    def test_packet_payload_and_timeout_fail(self):
        log = dict(total=1, records=[dict(sequence=0, timeout=False, packet='00' * 23)])
        self.assertEqual(compare(log, [bytes(23)]), 1)
        for packets in ([], [bytes([1]) * 23]):
            with self.assertRaises(ValueError):
                compare(log, packets)
        log['records'][0]['timeout'] = True
        with self.assertRaises(ValueError):
            compare(log, [bytes(23)])

    def test_timing_excludes_short_line(self):
        rows = [['1', '10', '12', '0', 'c0e083'], ['1', '12', '1222', '1', 'c0e22e'],
                ['2', '239', '12', '0', 'c0e083'], ['2', '242', '12', '1', 'c0e22e']]
        result = timing(rows)
        self.assertEqual(result['master_clock_histogram'], {3938: 1})
        self.assertEqual(len(result['excluded']), 1)
        with self.assertRaises(ValueError):
            timing(rows[:-1])
