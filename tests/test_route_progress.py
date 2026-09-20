import unittest
from tools.audit_route_progress import compare, visits


def rows(rooms):
    result = []
    for frame, room in enumerate(rooms, 1):
        memory = bytearray(2048)
        memory[0x42] = room
        result.append(dict(frame=frame, phase='route', game_ram_hex=memory.hex()))
    return result


class RouteProgressTests(unittest.TestCase):
    def test_missing_room_fails(self):
        self.assertFalse(compare(rows([0, 1, 2, 3]), rows([0, 1, 1, 1]))['room_sequence_matches'])

    def test_timing_is_not_hidden_but_not_a_sequence_gate(self):
        report = compare(rows([0, 1, 2]), rows([0, 0, 1, 2]))
        self.assertTrue(report['room_sequence_matches'])
        self.assertEqual(report['candidate_visits'][1]['frame'], 3)

    def test_revisits_preserved(self):
        self.assertEqual([v['room'] for v in visits(rows([0, 1, 1, 0]))], [0, 1, 0])

    def test_missing_ram_rejected(self):
        with self.assertRaises(ValueError):
            visits([dict(frame=1, phase='route', game_ram_hex='00')])
