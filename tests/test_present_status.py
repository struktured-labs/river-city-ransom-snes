import tempfile
import unittest
from pathlib import Path

from tools.check_present_status import STAT_ROWS, check_state_values, state_digits


class PresentStatusTests(unittest.TestCase):
    def fixture(self,folder):
        ram=bytearray(2048)
        for stat in range(10):
            for player in (0,1):ram[0x49f+stat*4+player]=stat*20+player
        (folder/'status.ram').write_bytes(ram)
        _,tiles=state_digits(ram)
        shadow=bytearray(2048)
        vram=bytearray(65536)
        slots=[row*32+col for row in STAT_ROWS for col in (12,13,14,27,28,29)]
        for i,tile in zip(slots,tiles):
            shadow[i]=tile
            vram[(0x2000+i)*2]=tile
        (folder/'status.nametable').write_bytes(shadow)
        (folder/'status.vram').write_bytes(vram)
        return slots

    def test_decimal_leading_zeroes_and_hundreds(self):
        ram=bytearray(2048)
        ram[0x49f:0x4a1]=bytes((0,105))
        values,tiles=state_digits(ram)
        self.assertEqual(values[:2],[0,105])
        self.assertEqual(tiles[:6],[0,0,0xf4,0xf5,0xf4,0xf9])

    def test_every_field_is_bound_to_current_values(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);self.fixture(p)
            self.assertTrue(check_state_values(p,'status')['passed'])
            ram=bytearray((p/'status.ram').read_bytes())
            ram[0x4c4]=63
            (p/'status.ram').write_bytes(ram)
            self.assertFalse(check_state_values(p,'status')['passed'])

    def test_last_published_digit_cannot_be_stale(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);slots=self.fixture(p)
            vram=bytearray((p/'status.vram').read_bytes())
            vram[(0x2000+slots[-1])*2]=0
            (p/'status.vram').write_bytes(vram)
            self.assertFalse(check_state_values(p,'status')['passed'])
