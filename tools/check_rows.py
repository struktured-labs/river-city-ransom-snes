"""Compare executed SNES row staging against an independent NES attribute oracle."""
import argparse
import itertools
from pathlib import Path
import struct
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def expected_rows(shadow, half):
    if len(shadow) != 4096 or half not in (0, 16):
        raise ValueError('Need four nametables and a valid pattern half')
    expected = bytearray(8192)
    for table in range(4):
        for y in range(30):
            for x in range(32):
                tile = shadow[table*1024+y*32+x]
                attr = shadow[table*1024+960+(y//4)*8+x//4]
                palette = (attr >> ((y%4//2)*4+(x%4//2)*2)) & 3
                word = tile | ((half != 0) << 8) | (palette << 10)
                struct.pack_into('<H', expected, table*2048+(y*32+x)*2, word)
    return expected


def check(core, out, source=None):
    source = source or ROOT/'snes/row_test.asm'
    out.mkdir(parents=True, exist_ok=True)
    (out/'native_palette.inc').write_text('.word '+','.join(['0']*64)+'\n')
    for half, task in itertools.product((0, 16), (0, 192)):
        subprocess.run([str(ROOT/'.deps/cc65/bin/ca65'), '-D', f'PATTERN_HALF={half}',
                        '-D', f'GAME_TASK={task}',
                        '-I', str(out), '-I', str(ROOT/'snes'), '-o', str(out/'row.o'), str(source)], check=True)
        subprocess.run([str(ROOT/'.deps/cc65/bin/ld65'), '-C', str(ROOT/'snes/native_boot.cfg'),
                        '-o', str(out/'row.bin'), str(out/'row.o')], check=True)
        rom = bytearray(2097152)
        rom[0x8000:0x10000] = (out/'row.bin').read_bytes()
        rom[0xFFDC:0xFFE0] = b'\xff\xff\0\0'
        checksum = sum(rom) & 65535
        struct.pack_into('<HH', rom, 0xFFDC, checksum^65535, checksum)
        cart, ram = out/f'row-{half}-{task}.sfc', out/f'row-{half}-{task}.ram'
        cart.write_bytes(rom)
        subprocess.run([sys.executable, str(ROOT/'tools/smoke_libretro.py'), '--core', str(core),
                        '--rom', str(cart), '--kind', 'adapter', '--frames', '600', '--ram', str(ram),
                        '--receipt', str(out/f'row-{half}-{task}.json')], check=True, capture_output=True, timeout=30)
        memory = ram.read_bytes()
        if memory[0x1C8E] != (2 if task == 192 else 4):
            raise RuntimeError('Producer did not respect its menu/gameplay row budget')
        if memory[0x12000:0x13000] != bytes((i^(i>>8)) & 255 for i in range(4096)):
            raise RuntimeError('Row fixture did not initialize the prescribed distinct nametables')
        expected = expected_rows(memory[0x12000:0x13000], half)
        if memory[0x3000:0x5000] != expected:
            raise RuntimeError('Executed row staging differs from the four-nametable attribute oracle')
    print('All 3840 visible tiles match the independent attribute oracle in both pattern halves.')


def negative_control(core):
    with tempfile.TemporaryDirectory(prefix='rcr-row-quadrant-') as temporary:
        out = Path(temporary)
        (out/'row_test.asm').write_text((ROOT/'snes/row_test.asm').read_text())
        source = (ROOT/'snes/native_prepare.asm').read_text()
        good = '    and #2\n    sta $12'
        if source.count(good) != 1:
            raise RuntimeError('Cannot identify vertical attribute quadrant selector')
        (out/'native_prepare.asm').write_text(source.replace(good, '    and #0\n    sta $12'))
        try:
            check(core, out, out/'row_test.asm')
        except RuntimeError as error:
            if 'differs from the four-nametable attribute oracle' not in str(error):
                raise
        else:
            raise RuntimeError('Wrong attribute quadrant passed the executed row oracle')
    print('Wrong vertical attribute quadrant fails the executed oracle.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--core', type=Path, required=True)
    parser.add_argument('--out', type=Path, default=ROOT/'build/row-oracle')
    args = parser.parse_args()
    check(args.core, args.out)
    negative_control(args.core)
