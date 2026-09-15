"""Execute production incremental graphics in a commercial-asset-free cartridge."""
import argparse
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


def check(core, out=None, source=None, negative=False, scrolling=False, late=False, expected_case=None, last_chr=False):
    out = out or ROOT / "build/video-test"
    source = source or ROOT / "snes/video_test.asm"
    out.mkdir(parents=True, exist_ok=True)
    palette = [0, 0x001F, 0x7C00] + [0] * 61
    (out / "native_palette.inc").write_text(".word " + ",".join(map(str, palette)) + "\n")
    subprocess.run([str(ROOT / ".deps/cc65/bin/ca65"), *(['-D','SCROLL_TEST=1'] if scrolling else []), *(['-D', 'LATE_TEST=1'] if late else []), *(['-D', 'LAST_CHR_TEST=1'] if last_chr else []), "-I", str(out), "-o", str(out / "test.o"),
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
            raise RuntimeError('Graphics mutation did not fail an executed assertion')
        if expected_case is not None and f'adapter case={expected_case}' not in result.stderr:
            raise RuntimeError('Graphics mutation failed at the wrong assertion')
        return
    result.check_returncode()
    actual = Image.open(screenshot).convert("RGB")
    if actual.size != (256, 239):
        raise RuntimeError("Unexpected SNES viewport")
    expected = Image.new("RGB", actual.size)
    expected.paste((255, 0, 0), (0, 0, 8, 8))
    if scrolling:
        expected.paste((255, 0, 0), (248, 56, 256, 64))
        expected.paste((255, 0, 0), (248, 192, 256, 194))
        expected.paste((255, 0, 0), (0, 194, 8, 200))
    else:
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
        good_split = '    lda #2\n    sta $420C'
        if original.count(good_split) != 1:
            raise RuntimeError('Split negative control no longer identifies exactly one enable')
        source.write_text(original.replace(good_split, '    lda #0\n    sta $420C'))
        try:
            check(core, out, out/'video_test.asm', scrolling=True)
        except RuntimeError as error:
            if 'differs from synthetic pixel oracle' not in str(error):
                raise
        else:
            raise RuntimeError('Disabling split scrolling incorrectly passed the pixel oracle')
    print('Lost-row consumer negative control failed the executed assertion as expected.')
    print('Disabled HDMA negative control failed the split-scroll pixel oracle as expected.')


def check_late_control(core):
    check(core, ROOT/'build/late-video-test', late=True)
    with tempfile.TemporaryDirectory(prefix='rcr-late-negative-') as temporary:
        out = Path(temporary)
        for name in ('video_test.asm', 'native_prepare.asm', 'native_video.asm'):
            (out/name).write_text((ROOT/'snes'/name).read_text())
        source = out/'native_video.asm'
        original = source.read_text()
        guard = '    bne @late\n    lda $1C7C\n    cmp #243\n    bcs @late\n    lda $4212\n    bmi @on_time\n@late:\n    rts\n@on_time:'
        if original.count(guard) != 1:
            raise RuntimeError('Late-entry negative control cannot identify guard')
        final_guard = '    jsr final_room\n    bcs :+\n    rts\n:\n'
        if original.count(final_guard) != 1:
            raise RuntimeError('Late-entry negative control cannot identify final guard')
        source.write_text(original.replace(guard, '').replace(final_guard, ''))
        check(core, out, out/'video_test.asm', late=True, negative=True)
    print('Late VBlank preserves queued graphics; removed-budget-guards control fails.')


def check_cache_controls(core):
    with tempfile.TemporaryDirectory(prefix='rcr-cache-negative-') as temporary:
        out = Path(temporary)
        for name in ('video_test.asm', 'native_prepare.asm', 'native_video.asm'):
            (out/name).write_text((ROOT/'snes'/name).read_text())
        source = out/'native_prepare.asm'
        original = source.read_text()
        mutations = (
            ('    cmp f:$7E5580,x\n    bne @snapshot',
             '    cmp f:$7E5580,x\n    nop\n    nop'),
            ('    cmp $1C86\n    bne @changed',
             '    cmp $1C86\n    nop\n    nop'),
        )
        for good, bad in mutations:
            if original.count(good) != 1:
                raise RuntimeError('Cache negative control cannot identify invalidation')
            source.write_text(original.replace(good, bad))
            check(core, out, out/'video_test.asm', negative=True, expected_case=7)
    print('Missing palette and sprite-pattern invalidation each fail cache assertion 7.')


def check_last_chr_control(core):
    check(core, ROOT/'build/last-chr-test', last_chr=True)
    with tempfile.TemporaryDirectory(prefix='rcr-last-chr-negative-') as temporary:
        out = Path(temporary)
        for name in ('video_test.asm', 'native_prepare.asm', 'native_video.asm'):
            (out/name).write_text((ROOT/'snes'/name).read_text())
        path = out/'native_video.asm'
        original = path.read_text()
        good = '    .repeat 11, pair\n        ora $1D82+pair*2'
        if original.count(good) != 1:
            raise RuntimeError('Cannot identify complete CHR queue reduction')
        path.write_text(original.replace(good, '    .repeat 10, pair\n        ora $1D82+pair*2'))
        check(core, out, out/'video_test.asm', negative=True, expected_case=8, last_chr=True)
    print('Final CHR slot drains and restores pixels; omitted bitmap word fails case 8.')


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core", type=Path, required=True)
    core = parser.parse_args().core
    check(core)
    check(core, ROOT/'build/scroll-test', scrolling=True)
    check_lost_row_control(core)
    check_late_control(core)
    check_cache_controls(core)
    check_last_chr_control(core)
