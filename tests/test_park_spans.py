import copy
import unittest

from tools.audit_park_spans import LABELS, analyze, parse


class ParkSpanTests(unittest.TestCase):
    def fixture(self):
        binding = dict(points={str(i): f'{0x8000+i:04x}' for i in LABELS}, first=100, last=102)
        # One late interval: first NMI, deferred camera exit, worker, poll, NMI.
        order = (0, 8, 7, 10, 11, 5, 6, 1, 2, 3, 4, 9, 9, 0)
        rows = []
        for n, event in enumerate(order):
            clock = 100000+n*5000 if n < len(order)-1 else 814732
            rows.append([str(v) for v in (event, 100 if n == 0 else 102 if n == 13 else 101,
                240 if n in (0, 13) else 20+n, 100, clock, f'{0xc08000+event:06x}',
                65535 if n == 0 else 0, 192, 0, 0, 3, 0, 1, 0, 1, 136)])
        return rows, binding

    def test_stages_and_waits_do_not_double_count(self):
        rows, binding = self.fixture()
        report = analyze(parse(rows, binding))
        self.assertEqual(report['stage_costs']['sprites → chr']['maximum'], 5000)
        gap = report['late_nmi_intervals'][0]
        self.assertEqual(gap['nominal_frames'], 2)
        self.assertEqual(gap['observed_poll_clocks'], 5000)
        self.assertEqual(sum(s['label'] == 'outside_vblank' for s in gap['stages']), 1)

    def test_reject_wrong_bank_for_exact_pc(self):
        rows, binding = self.fixture()
        binding['points']['0'] = '008000'
        with self.assertRaisesRegex(ValueError, 'PC'):
            parse(rows, binding)

    def test_exact_bank_zero_supported(self):
        rows, binding = self.fixture()
        binding['points']['0'] = '008000'
        for r in rows:
            if r[0] == '0':
                r[5] = '008000'
        self.assertEqual(len(parse(rows, binding)), len(rows))

    def test_reject_clock_reset_and_missing_points(self):
        rows, binding = self.fixture()
        rows[4][4] = '1'
        with self.assertRaisesRegex(ValueError, 'Nonmonotonic'):
            parse(rows, binding)
        rows, binding = self.fixture()
        with self.assertRaisesRegex(ValueError, 'coverage'):
            parse([r for r in rows if r[0] != '3'], binding)

    def test_no_bridge_across_interrupt_or_pause(self):
        rows, binding = self.fixture()
        parsed = parse(rows, binding)
        # A pause anywhere in the interval invalidates the stable NMI-gap sample.
        paused = copy.deepcopy(parsed)
        paused[-2]['pause'] = 32
        self.assertFalse(analyze(paused)['late_nmi_intervals'])
        # Sprite start and tail under different NMI generations cannot be paired.
        interrupted = copy.deepcopy(parsed)
        interrupted[10]['nmi'] = 1
        with self.assertRaisesRegex(ValueError, 'No stable observations'):
            analyze(interrupted)

    def test_bad_width_and_bounds(self):
        rows, binding = self.fixture()
        rows[0].pop()
        with self.assertRaisesRegex(ValueError, 'sixteen'):
            parse(rows, binding)
        rows, binding = self.fixture()
        binding['last'] = 101
        with self.assertRaisesRegex(ValueError, 'outside'):
            parse(rows, binding)


if __name__ == '__main__':
    unittest.main()
