import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class RectDmaSourceControls(unittest.TestCase):
    def test_dma_path_is_guarded_and_has_page_remap(self):
        source = (ROOT / 'snes/native_runtime.asm').read_text()
        block = source.split('; The guarded run is a constant-byte fill', 1)[1].split('.endif', 1)[0]
        self.assertIn('mvn $7F0000,$7F0000', block)
        self.assertIn('jsr mark_ppu_dirty', block)
        self.assertIn('jsr ppu_pointer', block)


if __name__ == '__main__':
    unittest.main()
