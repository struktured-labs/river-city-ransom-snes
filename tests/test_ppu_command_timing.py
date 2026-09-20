import tempfile
import unittest
from pathlib import Path

from tools.analyze_ppu_command_timing import analyze, read_commands, unique_anchor


def write(path, rows):
    path.write_text(''.join(','.join(map(str, row)) + '\n' for row in rows))


def nes(frame, pc, value, register='2006'):
    return [frame, 240, frame * 100, pc, register, value]


def snes(frame, pc, value, transition=0, depth=1):
    return [frame, 6, 100, f'c7{pc}', value, 0, 0, 0, 0, 192, 1,
            transition, 1, 0, depth, 0]


class PpuCommandTimingTests(unittest.TestCase):
    def test_exact_anchor_reports_generation_and_visibility_delta(self):
        with tempfile.TemporaryDirectory() as tmp:
            nes_path, snes_path = Path(tmp) / 'nes.csv', Path(tmp) / 'snes.csv'
            write(nes_path, [nes(10, 'c52a', 32), nes(10, 'c535', 67)])
            write(snes_path, [snes(13, 'c52a', 32), snes(13, 'c535', 67)])
            report = analyze(nes_path, snes_path, 0x2043, 1)
            self.assertEqual(report['measurements']['generation_frame_delta'], 3)
            self.assertEqual(report['measurements']['visible_frame_delta'], 4)
            self.assertEqual(report['anchor']['snes']['transition_state'], 0)
            self.assertFalse(report['passed'])

    def test_low_byte_without_high_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'bad.csv'
            write(path, [nes(1, 'c535', 67)])
            with self.assertRaisesRegex(ValueError, 'no preceding high'):
                read_commands(path, 'nes')

    def test_cross_frame_pair_uses_low_store_as_completion(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'trace.csv'
            write(path, [snes(1, 'c52a', 32), snes(2, 'c535', 67)])
            command = read_commands(path, 'snes')[0]
            self.assertEqual((command.high_frame, command.frame, command.address),
                             (1, 2, 0x2043))

    def test_missing_or_duplicate_anchor_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'trace.csv'
            write(path, [nes(1, 'c52a', 32), nes(1, 'c535', 67),
                         nes(2, 'c52a', 32), nes(2, 'c535', 67)])
            commands = read_commands(path, 'nes')
            with self.assertRaisesRegex(ValueError, 'occurs 2 times'):
                unique_anchor(commands, 0x2043, 'NES')
            with self.assertRaisesRegex(ValueError, 'occurs 0 times'):
                unique_anchor(commands, 0x9999, 'NES')

    def test_sequence_alignment_disambiguates_later_candidate_repeat(self):
        with tempfile.TemporaryDirectory() as tmp:
            nes_path, snes_path = Path(tmp) / 'nes.csv', Path(tmp) / 'snes.csv'
            write(nes_path, [nes(8, 'c52a', 0x20), nes(8, 'c535', 0x23),
                             nes(10, 'c52a', 0x20), nes(10, 'c535', 0x43)])
            write(snes_path, [snes(11, 'c52a', 0x20), snes(11, 'c535', 0x23),
                              snes(13, 'c52a', 0x20), snes(13, 'c535', 0x43),
                              snes(20, 'c52a', 0x20), snes(20, 'c535', 0x43)])
            report = analyze(nes_path, snes_path, 0x2043)
            self.assertEqual(report['anchor']['snes_occurrences'], 2)
            self.assertEqual(report['measurements']['snes_generation_frame'], 13)

    def test_wrong_nes_register_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'bad.csv'
            write(path, [nes(1, 'c52a', 32, '2007')])
            with self.assertRaisesRegex(ValueError, r'did not write \$2006'):
                read_commands(path, 'nes')


if __name__ == '__main__':
    unittest.main()
