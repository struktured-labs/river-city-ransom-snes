import unittest
from pathlib import Path
from tools.build_native import build


class RasterLineTests(unittest.TestCase):
    def test_nondefault_line_requires_raster(self):
        with self.assertRaisesRegex(ValueError, 'Raster line'):
            build(Path('/nonexistent-input'), [], Path('/nonexistent-output'), raster_line=200)

    def test_out_of_range_rejected_before_io(self):
        for line in (0, 221, -1, 256):
            with self.subTest(line=line), self.assertRaisesRegex(ValueError, 'Raster line'):
                build(Path('/nonexistent-input'), [], Path('/nonexistent-output'),
                      experimental_raster=True, raster_line=line)
