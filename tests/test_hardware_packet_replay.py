import unittest

from tools.audio_packet_log import decode
from tools.build_hardware_packet_replay import payload
from tests.test_audio_packet_log import fixture


class HardwareReplayTests(unittest.TestCase):
    def test_exact_records_and_nmi_wrap(self):
        records = decode(fixture(65538))['records'][-3:]
        self.assertEqual(payload(records), b''.join(b'\x01' + bytes.fromhex(r['packet']) for r in records))

    def test_missing_sequence_gap_timeout_and_short_packet_rejected(self):
        for field, value in (('sequence', 10), ('nmi', 10), ('timeout', True), ('packet', '00')):
            records = decode(fixture(3))['records']
            records[1][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                payload(records)

    def test_empty_and_oversized_rejected(self):
        for records in ([], decode(fixture(3000))['records']):
            with self.assertRaises(ValueError):
                payload(records)


if __name__ == '__main__':
    unittest.main()
