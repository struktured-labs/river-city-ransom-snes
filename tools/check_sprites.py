"""Exhaustive original-attribute to staged SNES OAM oracle, using production code."""
import argparse
from pathlib import Path
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def check(core, out, corrupt_attribute=None):
    out.mkdir(parents=True, exist_ok=True)
    (out/'native_palette.inc').write_text('.word '+','.join(['0']*64)+'\n')
    for half in (0, 8):
        for group in range(4):
            prefix = out/f'sprites-{half}-{group}'
            subprocess.run([str(ROOT/'.deps/cc65/bin/ca65'),
                            '-D', 'PATTERN_HALF=0', '-D', 'GAME_TASK=0', '-D', 'MIRROR_MODE=0',
                            '-D', f'SPRITE_HALF={half}', '-D', f'ATTRIBUTE_GROUP={group}',
                            '-I', str(out), '-I', str(ROOT/'snes'), '-o', str(prefix.with_suffix('.o')),
                            str(ROOT/'snes/row_test.asm')], check=True)
            subprocess.run([str(ROOT/'.deps/cc65/bin/ld65'), '-C', str(ROOT/'snes/native_boot.cfg'),
                            '-o', str(prefix.with_suffix('.bin')), str(prefix.with_suffix('.o'))], check=True)
            rom = bytearray(2097152)
            rom[0x8000:0x10000] = prefix.with_suffix('.bin').read_bytes()
            if corrupt_attribute is not None:
                table = bytes((a & 192) + (a % 4)*2 + (0 if a & 32 else 48) for a in range(256))
                if rom.count(table) != 1:
                    raise RuntimeError('Cannot identify the complete sprite attribute lookup')
                rom[rom.index(table)+corrupt_attribute] ^= 64
            rom[0xFFDC:0xFFE0] = b'\xff\xff\0\0'
            checksum = sum(rom) & 65535
            struct.pack_into('<HH', rom, 0xFFDC, checksum ^ 65535, checksum)
            cart = prefix.with_suffix('.sfc')
            cart.write_bytes(rom)
            ram = prefix.with_suffix('.ram')
            subprocess.run([sys.executable, str(ROOT/'tools/smoke_libretro.py'), '--core', str(core),
                            '--rom', str(cart), '--kind', 'adapter', '--frames', '300', '--ram', str(ram),
                            '--receipt', str(prefix.with_suffix('.json'))], check=True, capture_output=True, timeout=30)
            memory = ram.read_bytes()
            expected = bytearray()
            for sprite in range(64):
                raw = group*64 + sprite
                flags = (raw & 192) + (raw % 4)*2 + (0 if raw & 32 else 48) + half//8
                coordinate = sprite*4
                expected.extend((coordinate, coordinate+2 if coordinate < 239 else 240, coordinate, flags))
            if memory[0x5000:0x5100] != expected:
                raise RuntimeError(f'Staged sprite mismatch: pattern half {half}, attribute group {group}')
    print('All 256 attributes, both pattern halves, coordinates and hidden Y values match staged OAM.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--core', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    check(args.core, args.out)
    for attribute in (0, 255):
        try:
            check(args.core, args.out/f'negative-{attribute}', corrupt_attribute=attribute)
        except RuntimeError as error:
            if not str(error).startswith('Staged sprite mismatch:'):
                raise
        else:
            raise RuntimeError('Corrupted attribute lookup passed the staged OAM oracle')
    print('Corrupting either endpoint of the attribute table fails the executed OAM oracle.')
