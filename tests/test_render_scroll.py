import csv
from pathlib import Path
import tempfile
import unittest

from tools.audit_render_scroll import bands, load_lines, nes_offset


class RenderScrollTests(unittest.TestCase):
    def test_fetch_coordinates_all_scroll_values(self):
        for scroll in range(512):
            for group in range(32):
                world = (scroll + group * 8) & 511
                address = 0x2000 | ((world >> 8) << 10) | ((world & 255) >> 3)
                following = address ^ 0x41f if address & 31 == 31 else address + 1
                self.assertEqual(nes_offset(dict(group=group, older_address=address,
                    newer_address=following, fine_x=scroll & 7, mask=24)), scroll)

    def test_broken_shifter_provenance_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Nonconsecutive'):
            nes_offset(dict(group=0, older_address=31, newer_address=32, fine_x=7, mask=24))
        with self.assertRaisesRegex(ValueError, 'Unsupported'):
            nes_offset(dict(group=0, older_address=0, newer_address=1, fine_x=0, mask=16))

    def test_midframe_split_is_retained(self):
        lines = {y: 253 if y < 159 else 255 for y in range(32, 192)}
        self.assertEqual(bands(lines), [dict(first_line=32, last_line=158, scroll_x=253),
            dict(first_line=159, last_line=191, scroll_x=255)])

    def test_missing_and_duplicate_lines_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'trace.csv'
            rows = [dict(frame=1, line=y, h_offset=253, v_offset=0, mode=0,
                main_screen=1, forced_blank=0) for y in range(32, 192)]
            for records, error in ((rows[:-1], 'Missing'), (rows + rows[:1], 'Duplicate')):
                with path.open('w') as stream:
                    writer = csv.DictWriter(stream, fieldnames=rows[0])
                    writer.writeheader()
                    writer.writerows(records)
                with self.assertRaisesRegex(ValueError, error):
                    load_lines(path, 'snes', [1])
