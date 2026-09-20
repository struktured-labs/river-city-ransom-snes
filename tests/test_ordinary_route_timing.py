import unittest

from tools.audit_ordinary_route_timing import cadence, context, sound_pairs, sound_timing


def row(frame, room=0, busy=False, pause=False):
    ram = bytearray(2048)
    ram[0x100] = 0xc0
    ram[0x692] = 4
    ram[0x42] = room
    ram[0x107] = 128 if busy else 0
    ram[0x3f] = 32 if pause else 0
    return dict(frame=frame, game_ram_hex=ram.hex())


def event(kind, frame, clock, stack=240):
    r = ['0']*50
    r[:5] = [str(frame), '240', str(clock), str(kind), 'fa54' if kind == 3 else 'fa64']
    r[5] = '192'; r[12] = str(stack)
    return r


class OrdinaryRouteTiming(unittest.TestCase):
    def test_busy_kept_pause_excluded(self):
        rows = [row(1), row(2, busy=True)]
        self.assertEqual(context(rows, 1, 2)['room'], 0)
        self.assertEqual(context(rows, 1, 2)['busy_frames'], [2])
        rows[1] = row(2, pause=True)
        self.assertIsNone(context(rows, 1, 2)['room'])
        with self.assertRaises(ValueError):
            context(rows, 0, 1)

    def test_slow_busy_loop_not_hidden(self):
        rows = [row(i, busy=(i == 2)) for i in range(1, 8)]
        loops = [dict(start=dict(frame=f, clock=f*100),
                      finish=dict(frame=f+1, clock=(f+1)*100), nmi_advances=n)
                 for f, n in ((1, 3), (4, 2), (6, 2))]
        r = cadence(loops, rows)['rooms']['0']
        self.assertEqual(r['frame_histogram'], {'3': 1, '2': 1})
        self.assertEqual(r['busy_intervals'], 1)
        self.assertEqual(len(r['off_cadence']), 1)
        self.assertFalse(r['passed'])

    def test_nonconsecutive_selection_does_not_invent_gap(self):
        rows = [row(i, pause=(i == 4)) for i in range(1, 8)]
        loops = [dict(start=dict(frame=f, clock=f*100),
                      finish=dict(frame=f+1, clock=(f+1)*100), nmi_advances=2)
                 for f in (1, 3, 5)]
        r = cadence(loops, rows)
        self.assertEqual(r['rooms']['0']['intervals'], 1)
        self.assertEqual(len(r['excluded']), 1)

    def test_sound_exact_duration_decomposition(self):
        pairs, censored = sound_pairs([event(3, 1, 100), event(4, 1, 130),
                                      event(3, 2, 200), event(4, 2, 250)])
        self.assertFalse(censored)
        r = sound_timing(pairs, [row(1, busy=True), row(2)])['intervals'][0]
        self.assertEqual((r['entry_gap_cycles'], r['duration_change_cycles'],
                          r['return_gap_cycles']), (100, 20, 120))
        self.assertEqual(r['context']['busy_frames'], [1])

    def test_sound_negative_controls(self):
        for records in ([event(3, 1, 100), event(4, 1, 150, stack=238)],
                        [event(3, 1, 100), event(3, 2, 200)],
                        [event(3, 2, 200), event(4, 1, 150)], []):
            with self.assertRaises(ValueError):
                sound_pairs(records)


if __name__ == '__main__':
    unittest.main()
