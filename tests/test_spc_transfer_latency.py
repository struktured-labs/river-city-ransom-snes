import unittest
from tools.analyze_spc_ack import analyze, completion_timing


def packet(end_frame=1, end_line=32, end_cycle=200):
    def row(frame, line, cycle, token, y):
        return ['S', str(frame), str(line), str(cycle), '1', str(token), str(y), 'c08c64']
    rows = [row(0, 0, 0, 0x7D, 0x2C02), row(1, 10, 100, 0x7D, 23),
            row(1, 10, 200, 0xD7, 23)]
    rows += [row(1, 10, 200, i, i) for i in range(22)]
    rows.append(row(end_frame, end_line, end_cycle, 22, 22))
    return rows


class TransferLatencyTests(unittest.TestCase):
    def test_frame_bin_gap_is_not_elapsed_duration(self):
        rows = [dict(frame=1, line=261, cycle=1300, absolute_clock=1000000),
                dict(frame=3, line=1, cycle=0, absolute_clock=1360000)]
        result = completion_timing(rows)
        self.assertEqual(result['completion_frame_gap_histogram'], {2: 1})
        timing = result['absolute_completion_timing']
        self.assertEqual(timing['mean_master_clocks'], 360000)
        self.assertEqual(timing['long_intervals'], [])
        rows[1]['absolute_clock'] = 1600000
        self.assertEqual(len(completion_timing(rows)['absolute_completion_timing']['long_intervals']), 1)

    def test_absolute_clock_includes_wrap_and_short_line(self):
        rows = packet(end_frame=2, end_line=0)
        # Emulate an interval spanning a 1360-clock short line and a normal line.
        clocks = [0, 100, 200] + [201+i for i in range(22)] + [200+1360+1364]
        for row, clock in zip(rows, clocks):
            row.append(str(clock))
        result = analyze(rows)['data_phase_timing']
        self.assertEqual(result['measured_packets'], 1)
        self.assertEqual(result['excluded_packets'], 0)
        self.assertEqual(result['mean_master_clocks'], 2724)
        rows[-1][-1] = '1'
        with self.assertRaisesRegex(ValueError, 'went backwards'):
            analyze(rows)

    def test_mixed_clock_formats_rejected(self):
        rows = packet()
        rows[-1].append('100000')
        with self.assertRaisesRegex(ValueError, 'Mixed'):
            analyze(rows)

    def test_same_frame_active_lines(self):
        result = analyze(packet())['data_phase_timing']
        self.assertEqual(result['measured_packets'], 1)
        self.assertEqual(result['mean_master_clocks'], 22*1364)

    def test_wrap_and_vblank_excluded(self):
        for rows in (packet(end_frame=2), packet(end_line=240)):
            result = analyze(rows)['data_phase_timing']
            self.assertEqual(result['excluded_packets'], 1)
            self.assertIsNone(result['mean_master_clocks'])

    def test_backwards_clock_rejected(self):
        with self.assertRaisesRegex(ValueError, 'went backwards'):
            analyze(packet(end_line=10, end_cycle=100))
