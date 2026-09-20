"""Compare executed SNES row staging against an independent NES attribute oracle."""
import argparse
import itertools
from pathlib import Path
import struct
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def expected_rows(shadow, half, mirror=0):
    if len(shadow) != 4096 or half not in (0, 16) or mirror not in (0, 1):
        raise ValueError('Need four nametables and a valid pattern half')
    expected = bytearray(8192)
    for table in range(4):
        physical = (table // 2) if mirror else (table % 2)
        for y in range(30):
            for x in range(32):
                tile = shadow[physical*1024+y*32+x]
                attr = shadow[physical*1024+960+(y//4)*8+x//4]
                palette = (attr >> ((y%4//2)*4+(x%4//2)*2)) & 3
                word = tile | ((half != 0) << 8) | (palette << 10)
                struct.pack_into('<H', expected, table*2048+(y*32+x)*2, word)
    return expected


def check(core, out, source=None, fast_scan=False, store_offsets=False, attribute_lookup=False,
          hidden_rows=None, transition_state=0, alias_word_copy=False, fused_alias_rows=False):
    source = source or ROOT/'snes/row_test.asm'
    out.mkdir(parents=True, exist_ok=True)
    (out/'native_palette.inc').write_text('.word '+','.join(['0']*64)+'\n')
    extra = ['-D', f'HIDDEN_ROW_BUDGET={hidden_rows}', '-D', f'TRANSITION_STATE={transition_state}'] if hidden_rows is not None else []
    if alias_word_copy:
        extra += ['-D', 'EXPERIMENTAL_ALIAS_WORD_COPY=1']
    if fused_alias_rows:
        if not attribute_lookup:raise ValueError('Fused rows require attribute lookup')
        extra += ['-D', 'EXPERIMENTAL_FUSED_ALIAS_ROWS=1']
    for half, task, mirror in itertools.product((0, 16), (0, 192), (0, 1)):
        subprocess.run([str(ROOT/'.deps/cc65/bin/ca65'), *extra, *(['-D', 'EXPERIMENTAL_ROW_SCAN=1'] if fast_scan else []), *(['-D', 'EXPERIMENTAL_ROW_STORES=1'] if store_offsets else []), *(['-D', 'EXPERIMENTAL_ATTRIBUTE_LOOKUP=1'] if attribute_lookup else []), '-D', f'PATTERN_HALF={half}',
                        '-D', f'GAME_TASK={task}',
                        '-D', f'MIRROR_MODE={mirror}',
                        '-I', str(out), '-I', str(ROOT/'snes'), '-o', str(out/'row.o'), str(source)], check=True)
        subprocess.run([str(ROOT/'.deps/cc65/bin/ld65'), '-C', str(ROOT/'snes/native_boot.cfg'),
                        '-o', str(out/'row.bin'), str(out/'row.o')], check=True)
        rom = bytearray(2097152)
        rom[0x8000:0x10000] = (out/'row.bin').read_bytes()
        rom[0xFFDC:0xFFE0] = b'\xff\xff\0\0'
        checksum = sum(rom) & 65535
        struct.pack_into('<HH', rom, 0xFFDC, checksum^65535, checksum)
        cart, ram = out/f'row-{half}-{task}-{mirror}.sfc', out/f'row-{half}-{task}-{mirror}.ram'
        cart.write_bytes(rom)
        subprocess.run([sys.executable, str(ROOT/'tools/smoke_libretro.py'), '--core', str(core),
                        '--rom', str(cart), '--kind', 'adapter', '--frames', '600', '--ram', str(ram),
                        '--receipt', str(out/f'row-{half}-{task}-{mirror}.json')], check=True, capture_output=True, timeout=30)
        memory = ram.read_bytes()
        first_flags = bytearray([1]*128)
        budget = (hidden_rows if hidden_rows is not None and transition_state == 2 else 2) if task == 192 else 4
        for row in range(budget):
            first_flags[row] = 2
            first_flags[row ^ (32 if mirror else 64)] = 2
        if memory[0x5800:0x5880] != first_flags:
            raise RuntimeError('First-batch flags differ from complete invalidation/alias oracle')
        if memory[0x1C8E] != budget*2:
            raise RuntimeError('Producer did not respect its menu/gameplay row budget')
        if memory[0x12000:0x13000] != bytes((i^(i>>8)) & 255 for i in range(4096)):
            raise RuntimeError('Row fixture did not initialize the prescribed distinct nametables')
        expected = expected_rows(memory[0x12000:0x13000], half, mirror)
        if memory[0x3000:0x5000] != expected:
            raise RuntimeError('Executed row staging differs from the four-nametable attribute oracle')
    print('All 3840 visible tiles match the independent attribute oracle in both pattern halves.')


def negative_control(core, fast_scan=False, store_offsets=False, attribute_lookup=False):
    with tempfile.TemporaryDirectory(prefix='rcr-row-quadrant-') as temporary:
        out = Path(temporary)
        (out/'row_test.asm').write_text((ROOT/'snes/row_test.asm').read_text())
        source = (ROOT/'snes/native_prepare.asm').read_text()
        if attribute_lookup:
            good = '(((attribute >> 4) & 3) << 10)'
            bad = '(((attribute >> 0) & 3) << 10)'
        else:
            good = ('sta f:$7E3000 + pair*4 + tile*2,x' if store_offsets
                    else '    and #2\n    sta $12')
            bad = ('sta f:$7E3000 + pair*4 + tile,x' if store_offsets
                   else '    and #0\n    sta $12')
        expected_occurrences = 2 if store_offsets and not attribute_lookup else 1
        if source.count(good) != expected_occurrences:
            raise RuntimeError('Cannot identify vertical attribute quadrant selector')
        (out/'native_prepare.asm').write_text(source.replace(good, bad))
        try:
            check(core, out, out/'row_test.asm', fast_scan, store_offsets, attribute_lookup)
        except RuntimeError as error:
            if 'differs from the four-nametable attribute oracle' not in str(error):
                raise
        else:
            raise RuntimeError('Wrong attribute quadrant passed the executed row oracle')
    print(('Wrong tile store offsets' if store_offsets else 'Wrong vertical attribute quadrant')
          + ' fails the executed oracle.')


def invalidation_negative_control(core):
    with tempfile.TemporaryDirectory(prefix='rcr-row-invalidation-') as temporary:
        out = Path(temporary)
        (out/'row_test.asm').write_text((ROOT/'snes/row_test.asm').read_text())
        source = (ROOT/'snes/native_prepare.asm').read_text()
        good = '    lda #126\n    mvn $7E0000,$7E0000'
        if source.count(good) != 1:
            raise RuntimeError('Cannot identify full row invalidation')
        (out/'native_prepare.asm').write_text(source.replace(good, '    lda #125\n    mvn $7E0000,$7E0000'))
        try:
            check(core, out, out/'row_test.asm')
        except RuntimeError as error:
            if 'First-batch flags differ' not in str(error):
                raise
        else:
            raise RuntimeError('Incomplete invalidation passed the complete flags oracle')
    print('Omitting the final invalidated row fails the complete flags oracle.')


def scan_negative_control(core):
    with tempfile.TemporaryDirectory(prefix='rcr-row-scan-') as temporary:
        out = Path(temporary)
        (out/'row_test.asm').write_text((ROOT/'snes/row_test.asm').read_text())
        source = (ROOT/'snes/native_prepare.asm').read_text()
        good = '    and #$0101'
        if source.count(good) != 1:
            raise RuntimeError('Cannot identify row scan dirty mask')
        (out/'native_prepare.asm').write_text(source.replace(good, '    and #$0000'))
        try:
            check(core, out, out/'row_test.asm', True)
        except RuntimeError as error:
            if (not any(message in str(error) for message in (
                    'First-batch flags differ', 'row budget', 'attribute oracle'))):
                raise
        else:
            raise RuntimeError('Skipping dirty rows passed the executed row oracle')
    print('Skipping dirty rows fails the executed oracle.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--core', type=Path, required=True)
    parser.add_argument('--out', type=Path, default=ROOT/'build/row-oracle')
    parser.add_argument('--grouped-scan', '--experimental-raster', dest='experimental_raster', action='store_true', help='Exercise the isolated grouped row scan; not enabled by game builds')
    parser.add_argument('--store-offsets', action='store_true', help='Exercise rejected game optimization in isolated tile oracle')
    parser.add_argument('--attribute-lookup', action='store_true', help='Exercise lookup-table row conversion in the independent tile oracle')
    args = parser.parse_args()
    check(args.core, args.out, fast_scan=args.experimental_raster, store_offsets=args.store_offsets, attribute_lookup=args.attribute_lookup)
    negative_control(args.core, args.experimental_raster, attribute_lookup=args.attribute_lookup)
    invalidation_negative_control(args.core)
    if args.store_offsets:
        negative_control(args.core, args.experimental_raster, store_offsets=True)
    if args.experimental_raster:
        scan_negative_control(args.core)
