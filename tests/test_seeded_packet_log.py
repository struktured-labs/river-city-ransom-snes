import unittest

from tools.audio_packet_log import decode
from tools.run_seeded_sram import seed_bytes


class SeededPacketLogTests(unittest.TestCase):
    def test_empty_seed_has_valid_pointer_and_no_committed_records(self):
        data = seed_bytes()
        self.assertEqual(len(data), 131072)
        self.assertEqual(data[32:], bytes(131072 - 32))
        decoded = decode(data)
        self.assertEqual(decoded['total'], 0)
        self.assertEqual(decoded['records'], [])
