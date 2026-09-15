import unittest
from tools.analyze_spc_ack import analyze, completion_timing


def event(token, y=0, frame=1):
    return ['S', frame, 3, 100, 1, token, y, '0088fa']


class SpcAckTests(unittest.TestCase):
    def test_scanline_zero_does_not_create_false_gap(self):
        rows = [dict(frame=370, line=2), dict(frame=370, line=0), dict(frame=372, line=2)]
        result = completion_timing(rows)
        self.assertEqual(result['completion_frame_gap_histogram'], {1: 2})
        self.assertEqual(result['raw_core_frame_gap_histogram'], {0: 1, 2: 1})
        self.assertEqual(result['gap_intervals'], [])

    def test_real_gap_is_retained(self):
        result = completion_timing([dict(frame=951, line=4), dict(frame=974, line=3)])
        self.assertEqual(result['gap_intervals'][0]['video_frame_gap'], 23)

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
