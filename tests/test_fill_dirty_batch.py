import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class FillDirtyBatchSourceControls(unittest.TestCase):
    def test_batch_is_guarded_to_aligned_four_page_fill(self):
        source = (ROOT / 'snes/native_runtime.asm').read_text()
        block = source.split('.ifdef EXPERIMENTAL_FILL_DIRTY_BATCH', 1)[1].split('.endif', 1)[0]
        self.assertIn('cpx #4', block)
        self.assertIn('lda a:$1C26', block)
        self.assertIn('and #3', block)
        self.assertIn('sta $09', block)


if __name__ == '__main__':
    unittest.main()
