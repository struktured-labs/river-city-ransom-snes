import csv
import tempfile
import unittest
from pathlib import Path

from tools.analyze_cpu_deadline import analyze


def row(system, *, a, ordinal, pointer, selector, mapper=(7, 2, 3)):
    width = 50 if system == "nes" else 56
    values = ["0"] * width
    if system == "nes":
        values[0], values[3], values[4], values[9] = str(900 + ordinal), "0", "cf04", str(a)
        values[18], values[24], values[25], values[26] = "1", str(ordinal), "16", "0"
        values[27:30], values[30:32], values[46] = map(str, mapper), map(str, pointer), str(selector)
    else:
        values[0], values[3], values[4], values[19] = str(900 + ordinal), "0", "c2cf04", str(a)
        values[22], values[28], values[29], values[30] = "1", str(ordinal), "16", "0"
        values[33:36], values[36:38], values[52] = map(str, mapper), map(str, pointer), str(selector)
    return values


class CpuDeadlineAnalysisTests(unittest.TestCase):
    def write(self, root, name, rows):
        path = root / name
        with path.open("w", newline="") as stream:
            csv.writer(stream, lineterminator="\n").writerows(rows)
        return path

    def test_classifies_rng_selected_stream_without_mapper_false_positive(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            nes = self.write(root, "nes.csv", [
                row("nes", a=211, ordinal=0, pointer=(23, 144), selector=8),
                row("nes", a=197, ordinal=1, pointer=(23, 144), selector=8),
            ])
            snes = self.write(root, "snes.csv", [
                row("snes", a=211, ordinal=0, pointer=(254, 143), selector=2),
                row("snes", a=198, ordinal=1, pointer=(254, 143), selector=2),
            ])
            report = analyze(nes, snes)["comparison"]
            self.assertEqual(report["classification"], "different-original-game-stream-selection")
            self.assertEqual(report["mapper_mismatch_count"], 0)
            self.assertTrue(report["gates"]["mapper_state_matches_on_paired_commands"])
            self.assertFalse(report["gates"]["rng_independent_speed_comparison_ready"])

    def test_rejects_old_malformed_28_column_nes_trace(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            nes = self.write(root, "nes.csv", [["0"] * 28])
            snes = self.write(root, "snes.csv", [row("snes", a=1, ordinal=0,
                                                      pointer=(0, 0), selector=0)])
            with self.assertRaisesRegex(ValueError, "unsupported/mixed widths"):
                analyze(nes, snes)


if __name__ == "__main__":
    unittest.main()
