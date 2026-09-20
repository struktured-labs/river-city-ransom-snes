import unittest

from tools.audit_combat_room_entry import first_entry


def row(room, mask):
    ram = bytearray(2048)
    ram[0x42], ram[0x100] = room, 0xc0
    return dict(game_ram_hex=ram.hex(), native=dict(ppu_mask=mask))


class FirstEntryTests(unittest.TestCase):
    def test_first_edge_not_later_convenient_entry(self):
        rows = [row(1, 0)] + [row(1, 8) for _ in range(40)]
        rows += [row(1, 0)] + [row(1, 8) for _ in range(40)]
        self.assertEqual(first_entry(rows, 1), 1)
        rows[20] = row(2, 8)
        with self.assertRaises(ValueError):
            first_entry(rows, 1)

    def test_edge_and_full_window_required(self):
        for rows in ([row(1, 8)]*41, [row(1, 0)]+[row(1, 8)]*39):
            with self.assertRaises(ValueError):
                first_entry(rows, 1)
        with self.assertRaises(ValueError):
            first_entry([row(0, 0)], 0)
