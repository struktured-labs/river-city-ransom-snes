import unittest

from tools.audio_packet_log import decode, MAGIC, SIZE, CAPACITY


def fixture(total):
    data = bytearray(SIZE)
    data[:8] = MAGIC
    data[8:12] = total.to_bytes(4, 'little')
    slot = 1 + total % CAPACITY
    data[12:14] = (0x6000 + slot % 256 * 32).to_bytes(2, 'little')
    data[14] = 0x20 + slot // 256
    for seq in range(max(0, total - CAPACITY), total):
        at = (1 + seq % CAPACITY) * 32
        data[at:at + 4] = seq.to_bytes(4, 'little')
        data[at + 4:at + 6] = (seq % 65536).to_bytes(2, 'little')
        data[at + 7:at + 30] = bytes((seq + x) % 256 for x in range(23))
        for byte in data[at:at + 30]:
            data[at + 30] ^= byte
        data[at + 31] = 0xA5
    return data


class PacketLogTests(unittest.TestCase):
    def test_empty_and_wrap(self):
        for count in (0, 1, 255, 256, 4094, 4095, 4096, 9000, 65537):
            report = decode(fixture(count))
            self.assertEqual(len(report['records']), min(count, CAPACITY))
            self.assertEqual(report['overwritten'], max(0, count - CAPACITY))
            if count:
                self.assertEqual(report['records'][-1]['sequence'], count - 1)

    def test_rejects_corruption_and_torn_records(self):
        for offset in (0, 8, 12, 14, 32, 39, 62, 63):
            data = fixture(2)
            data[offset] ^= 1
            with self.assertRaises(ValueError, msg=str(offset)):
                decode(data)
        with self.assertRaises(ValueError):
            decode(fixture(2)[:-1])

    def test_rejects_missing_sequence_even_with_valid_xor(self):
        data = fixture(3)
        data[32:64] = data[64:96]
        with self.assertRaises(ValueError):
            decode(data)

    def test_timeout_is_retained_not_success(self):
        data = fixture(1)
        data[38] = 1
        data[62] ^= 1
        self.assertTrue(decode(data)['records'][0]['timeout'])
