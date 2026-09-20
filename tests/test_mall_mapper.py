import unittest
from tools.check_mall_mapper import checkpoint


class MallMapperTests(unittest.TestCase):
    def row(self, room=2, pending=0):
        ram = bytearray(2048)
        ram[0x42] = room
        return dict(phase='observe_alley_exit', game_ram_hex=ram.hex(),
                    nes_mapper={'registers': [8, 10, 64, 66, 83, 65, 12, 13]},
                    native={'chr_registers': [8, 10, 64, 66, 69, 65],
                            'chr_jobs_pending': pending})

    def test_stale_bank_remains_a_difference(self):
        rows = [self.row()]
        self.assertNotEqual(checkpoint(rows, 'nes'), checkpoint(rows, 'snes'))
        rows[0]['native']['chr_registers'][4] = 83
        self.assertEqual(checkpoint(rows, 'nes'), checkpoint(rows, 'snes'))

    def test_wrong_room_rejected(self):
        with self.assertRaises(ValueError):
            checkpoint([self.row(room=1)], 'snes')

    def test_pending_upload_rejected(self):
        with self.assertRaises(ValueError):
            checkpoint([self.row(pending=1)], 'snes')
