import unittest

from tools.audit_camera_cadence import measure, parse_nes


def rows(count):
    ram = bytearray(2048)
    ram[0x42] = 3
    ram[0x100] = 192
    return [dict(frame=i+1, phase='park', game_ram_hex=ram.hex()) for i in range(count)]


class CameraCadenceTests(unittest.TestCase):
    def test_uses_clocks_not_integer_frame_gaps(self):
        events = [dict(frame=i*2+1, line=40, clock=i*200) for i in range(102)]
        result = measure(events, rows(203), 'park', 100)
        self.assertEqual(result['mean'], 2)
        events[50]['clock'] += 30
        result = measure(events, rows(203), 'park', 100)
        self.assertEqual(result['maximum'], 2.3)
        self.assertEqual(result['minimum'], 1.7)
        self.assertEqual(result['mean'], 2)

    def test_intermediate_pause_excludes_interval(self):
        events = [dict(frame=i*2+1, line=40, clock=i*200) for i in range(103)]
        timeline = rows(205)
        ram = bytearray.fromhex(timeline[100]['game_ram_hex'])
        ram[0x3f] = 32
        timeline[100]['game_ram_hex'] = ram.hex()
        result = measure(events, timeline, 'park', 100)
        self.assertEqual(result['count'], 100)

    def test_requires_coverage_and_monotonic_events(self):
        with self.assertRaisesRegex(ValueError, 'coverage'):
            measure([dict(frame=1, clock=1), dict(frame=2, clock=2)], rows(2), 'park', 100)
        with self.assertRaisesRegex(ValueError, 'Invalid camera'):
            measure([dict(frame=1, clock=2), dict(frame=2, clock=1)], rows(2), 'park', 100)

    def test_parser_excludes_other_writers_and_rejects_substitution(self):
        records = [['1', '240', '20', 'ffac', '00f6', '0'],
                   ['2', '44', '30', 'e2b1', '00f6', '42']]
        self.assertEqual(len(parse_nes(records, 1, 3)), 1)
        for bad in (records+records[-1:], [records[-1][:-1]], records[:1]):
            with self.assertRaises(ValueError):
                parse_nes(bad, 1, 3)
