"""Compile native startup in CI without any original game assets."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class NativeAssembly(unittest.TestCase):
    def test_color_entry_width_and_explicit_wram_store(self):
        ca65, ld65 = [ROOT / ".deps/cc65/bin" / name for name in ("ca65", "ld65")]
        if not ca65.exists() or not ld65.exists():
            self.fail("Run make bootstrap before native assembly tests")
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            (out / "native_palette.inc").write_text(".word " + ",".join(["0"] * 64) + "\n")
            subprocess.run([str(ca65), "-g", "-I", str(out), "--bin-include-dir",
                            str(ROOT / ".deps/upernes/source/asm"), "-o", str(out / "boot.o"),
                            str(ROOT / "snes/native_boot.asm")], check=True)
            subprocess.run([str(ld65), "-C", str(ROOT / "snes/native_boot.cfg"),
                            "-Ln", str(out / "boot.lbl"), "-o", str(out / "boot.bin"),
                            str(out / "boot.o")], check=True)
            labels = {line.split()[2].lstrip("."): int(line.split()[1], 16)
                      for line in (out / "boot.lbl").read_text().splitlines()}
            image = (out / "boot.bin").read_bytes()
            start = labels["native_color"] - 0x8000
            self.assertEqual(image[start:start + 4], bytes.fromhex("293fc220"))
            self.assertIn(bytes.fromhex("9f00307e"), image)
            self.assertIn(bytes.fromhex("9f00387e"), image)
