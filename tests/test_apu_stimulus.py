import unittest
from tools.replay_nes_apu_stimulus import pack_writes, publication_writes


def write(frame, index, value):
    return ['W', str(frame), '240', '100', '1', str(index), str(value), 'c12345']


class ApuStimulusTests(unittest.TestCase):
    def test_publication_keeps_boundary_and_repeated_write_order(self):
        packet = lambda f: [['P',str(f),'20','10','1',str(i),'0','c01234'] for i in range(23)]
        rows = [write(1,0,240), *packet(1), write(1,12,51), write(1,12,51),
                write(2,0,243), *packet(2)]
        shifted, mapping = publication_writes(rows)
        payload, grouped = pack_writes(shifted, 2)
        self.assertEqual(grouped, [[(0,240)], [(12,51),(12,51),(0,243)]])
        self.assertEqual([r['publication_frame'] for r in mapping], [1,2,2,2])
        self.assertEqual([r['write_frame'] for r in mapping], [1,1,1,2])
        self.assertEqual([r[2:] for r in shifted], [r[2:] for r in rows if r[0]=='W'])

    def test_publication_rejects_incomplete_reordered_and_interleaved_events(self):
        p = ['P','1','20','10','1','0','0','c01234']
        for rows in ([write(1,0,0)], [p], [p,p], [p,write(1,0,0)], []):
            with self.assertRaises(ValueError):
                publication_writes(rows)

    def test_empty_frames_and_repeated_resets_retained(self):
        packed, grouped = pack_writes([write(2, 3, 0), write(2, 3, 0), write(4, 0, 63)], 4)
        self.assertEqual(packed, bytes([0, 2, 3, 0, 3, 0, 0, 1, 0, 63]))
        self.assertEqual(grouped[1], [(3, 0), (3, 0)])

    def test_unknown_dmc_and_controller_side_effects_fail(self):
        for index in (16, 17, 18, 19, 20, 22, 24):
            with self.assertRaisesRegex(ValueError, 'Unsupported'):
                pack_writes([write(1, index, 0)], 1)
        with self.assertRaisesRegex(ValueError, 'Unsupported'):
            pack_writes([write(1, 21, 16)], 1)

    def test_order_and_execution_budget_fail_closed(self):
        with self.assertRaisesRegex(ValueError, 'ordering'):
            pack_writes([write(2, 0, 0), write(1, 0, 0)], 2)
        with self.assertRaisesRegex(ValueError, 'execution budget'):
            pack_writes([write(1, 0, 0)]*129, 1)

    def test_prefix_does_not_invent_later_writes(self):
        packed, grouped = pack_writes([write(1, 0, 63), write(3, 0, 0)], 2)
        self.assertEqual(packed, bytes([1, 0, 63, 0]))
        self.assertEqual(grouped, [[(0, 63)], []])

    def test_banked_capacity_and_counter_limits(self):
        writes = [write(i, 0, 63) for i in range(1, 12001)]
        with self.assertRaisesRegex(ValueError, 'ROM capacity'):
            pack_writes(writes, 12000)
        packed, _ = pack_writes(writes, 12000, banked=True)
        self.assertEqual(len(packed), 36000)
        with self.assertRaisesRegex(ValueError, 'ROM capacity'):
            pack_writes([write(i, 0, 63) for i in range(1, 40001)], 40000, banked=True)
        for frames in (0, -1, 65536):
            with self.assertRaisesRegex(ValueError, 'Frame counter'):
                pack_writes([], frames, banked=True)
