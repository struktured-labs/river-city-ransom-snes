from pathlib import Path
import tempfile
import unittest

from tools.build_balanced_pitch_review import windows


class BalancedPitchReviewTests(unittest.TestCase):
    def test_half_open_window_has_twelve_even_on_sample_boundary(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'pitch.csv'
            path.write_text(''.join(f'{tick},0,0,0,123,0,0,0,0,0,0,0,0\n' for tick in range(32,1025,32)))
            result=windows(path,[(0,512),(0,513)])
            self.assertEqual([len(r) for r in result],[12,12])
            self.assertEqual(result[0][0]['tick'],320)
            self.assertEqual(result[0][-1]['tick'],672)
            self.assertEqual(result[1][0]['tick'],352)

    def test_missing_sample_is_not_a_plot_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'pitch.csv'
            path.write_text(''.join(f'{tick},0,0,0,123,0,0,0,0,0,0,0,0\n'
                for tick in range(32,1025,32) if tick!=512))
            with self.assertRaises(ValueError):windows(path,[(0,512)])
