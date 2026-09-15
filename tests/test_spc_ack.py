import unittest
from tools.analyze_spc_ack import analyze


def event(token, y=0, frame=1):
    return ['S', frame, 3, 100, 1, token, y, '0088fa']


class SpcAckTests(unittest.TestCase):
    def fixture(self):
        return [event(0x7d, 0x2c02), event(0x7d), event(0xd7)] + [event(i, i) for i in range(23)]

    def test_complete_packet(self):
        self.assertEqual(analyze(self.fixture())['acknowledged_packets'], 1)

    def test_bad_missing_timeout_and_truncated(self):
        good = self.fixture()
        timeout = [r[:] for r in good]
        timeout[-1][0] = 'T'
        wrong_y = [r[:] for r in good]
        wrong_y[-1][6] = 21
        for rows in ([], good[:-1], good[:5]+good[6:], good[1:], timeout, wrong_y):
            with self.assertRaises(ValueError):
                analyze(rows)
