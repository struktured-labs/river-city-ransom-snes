import unittest

from tools.check_packet_log_timeouts import mutate


class TimeoutMutationTests(unittest.TestCase):
    def test_only_sender_calls_and_checked_padding(self):
        logger = bytes(128) + bytes.fromhex('2053d2') * 14
        image = bytearray(b'\xff' * 65536)
        image[0xE000:0xE000 + len(logger)] = logger
        changed = mutate(image, logger, 0xD253, 22)
        self.assertEqual(changed[0xE080:0xE000 + len(logger)], bytes.fromhex('2000ef') * 14)
        self.assertEqual(changed[0xEF00:0xEF09], bytes.fromhex('c916d00238604c53d2'))
        image[0xEF00] = 0
        with self.assertRaises(ValueError):
            mutate(image, logger, 0xD253, 22)

    def test_rejects_wrong_stage_and_call_count(self):
        with self.assertRaises(ValueError):
            mutate(bytes(65536), bytes(128), 0xD253, 1)
        with self.assertRaises(ValueError):
            mutate(bytes(65536), bytes(128), 0xD253, 0)
