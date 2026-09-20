import unittest

from tools.build_bridge_packet_log import BRIDGE, PREFIX, SUFFIX, trim


class BridgePacketLogTests(unittest.TestCase):
    def test_only_saves_removed(self):
        code = bytes(128) + PREFIX + b'body' + SUFFIX
        result = trim(code, BRIDGE)
        self.assertEqual(result, bytes(128) + bytes.fromhex('20bcd2088b') + b'body' + bytes.fromhex('e220ab2860'))
        self.assertEqual(len(code) - len(result), 12)

    def test_any_caller_byte_change_rejected(self):
        code = bytes(128) + PREFIX + b'body' + SUFFIX
        for index in range(len(BRIDGE)):
            bad = bytearray(BRIDGE)
            bad[index] ^= 1
            with self.assertRaises(ValueError):
                trim(code, bad)
        for index in (128, 134, len(code) - 2):
            bad = bytearray(code)
            bad[index] ^= 1
            with self.assertRaises(ValueError):
                trim(bad, BRIDGE)
