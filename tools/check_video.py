"""Execute production incremental graphics in a commercial-asset-free cartridge."""
import argparse
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


def check(core, out=None, source=None, negative=False):
    out = out or ROOT / "build/video-test"
    source = source or ROOT / "snes/video_test.asm"
    out.mkdir(parents=True, exist_ok=True)
    palette = [0, 0x001F, 0x7C00] + [0] * 61
    (out / "native_palette.inc").write_text(".word " + ",".join(map(str, palette)) + "\n")
    subprocess.run([str(ROOT / ".deps/cc65/bin/ca65"), "-I", str(out), "-o", str(out / "test.o"),
                    str(source)], check=True)
    subprocess.run([str(ROOT / ".deps/cc65/bin/ld65"), "-C", str(ROOT / "snes/native_boot.cfg"),
                    "-o", str(out / "test.bin"), str(out / "test.o")], check=True)
    image = bytearray(b"\0" * 2097152)
    image[0x8000:0x10000] = (out / "test.bin").read_bytes()
    # Synthetic tile 1: all pixels have original NES palette index 1.
    image[0x90010:0x90020] = bytes((255, 0)) * 8
    image[0xB0020:0xB0030] = bytes((255, 0)) * 8
    image[0xFFDC:0xFFE0] = b"\xff\xff\0\0"
    checksum = sum(image) & 65535
    struct.pack_into("<HH", image, 0xFFDC, checksum ^ 65535, checksum)
    rom, screenshot = out / "video-test.sfc", out / "screen.png"
    rom.write_bytes(image)
    result = subprocess.run([sys.executable, str(ROOT / "tools/smoke_libretro.py"), "--core", str(core),
                    "--rom", str(rom), "--kind", "adapter", "--frames", "600",
                    "--screenshot", str(screenshot), "--receipt", str(out / "receipt.json")],
                    capture_output=negative, text=True, timeout=30)
    if negative:
        if not result.returncode or 'WRAM status=ee' not in result.stderr:
            raise RuntimeError('Lost-row mutation did not fail an executed graphics assertion')
        return
    result.check_returncode()
    actual = Image.open(screenshot).convert("RGB")
    if actual.size != (256, 239):
        raise RuntimeError("Unexpected SNES viewport")
    expected = Image.new("RGB", actual.size)
    expected.paste((255, 0, 0), (0, 0, 8, 8))
    expected.paste((255, 0, 0), (0, 56, 8, 64))
    expected.paste((255, 0, 0), (0, 192, 8, 200))
    # Assert the producer's explicit SNES OAM coordinate (NES byte 15 + 2).
    # NES/SNES capture alignment is tested separately against original frames.
    expected.paste((0, 0, 255), (32, 17, 40, 25))
    if actual.tobytes() != expected.tobytes():
        raise RuntimeError("Incremental BG/OBJ/palette output differs from synthetic pixel oracle")
    print("Native producer, bounded NMI queue draining and exact BG/OBJ pixels passed.")


def check_lost_row_control(core):
    # Mutate only a disposable copy; production assembly stays untouched.
    with tempfile.TemporaryDirectory(prefix='rcr-row-negative-') as temporary:
        out = Path(temporary)
        for name in ('video_test.asm', 'native_prepare.asm', 'native_video.asm'):
            (out/name).write_text((ROOT/'snes'/name).read_text())
        source = out/'native_video.asm'
        good = '    lda $1D00,x\n    and #2\n    beq @next_row'
        bad = '    lda $1D00,x\n    cmp #2\n    bne @next_row'
        original = source.read_text()
        if original.count(good) != 1:
            raise RuntimeError('Negative control mutation no longer identifies exactly one consumer')
        source.write_text(original.replace(good, bad))
        check(core, out, out/'video_test.asm', negative=True)
    print('Lost-row consumer negative control failed the executed assertion as expected.')


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core", type=Path, required=True)
    core = parser.parse_args().core
    check(core)
    check_lost_row_control(core)
