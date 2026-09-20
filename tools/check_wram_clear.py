"""Execute the production reset clear against all 128KiB of poisoned WRAM."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def check(core, out):
    out.mkdir(parents=True, exist_ok=False)
    subprocess.run([str(ROOT/'.deps/cc65/bin/ca65'), '-I', str(ROOT/'snes'),
                    '-o', str(out/'test.o'), str(ROOT/'snes/wram_clear_test.asm')], check=True)
    subprocess.run([str(ROOT/'.deps/cc65/bin/ld65'), '-C', str(ROOT/'snes/native_boot.cfg'),
                    '-Ln', str(out/'test.lbl'), '-o', str(out/'test.bin'), str(out/'test.o')], check=True)
    base = bytearray(2097152)
    base[0x8000:0x10000] = (out/'test.bin').read_bytes()
    pair = bytes.fromhex('a00400a20080')
    if base.count(pair) != 1:
        raise RuntimeError('Cannot identify the four reset DMA transfers')
    results = []
    for name, replacement, expected_nonzero in (
            ('complete', pair, 0),
            ('missing-second-bank', bytes.fromhex('a00200a20080'), 65536),
            ('only-first-quarter', bytes.fromhex('a00100a20080'), 98304)):
        rom = bytearray(base.replace(pair, replacement))
        rom[0xFFDC:0xFFE0] = b'\xff\xff\0\0'
        checksum = sum(rom) & 65535
        struct.pack_into('<HH', rom, 0xFFDC, checksum ^ 65535, checksum)
        cart, ram = out/f'{name}.sfc', out/f'{name}.ram'
        cart.write_bytes(rom)
        subprocess.run([sys.executable, str(ROOT/'tools/smoke_libretro.py'), '--core', str(core),
                        '--rom', str(cart), '--kind', 'render', '--frames', '120', '--ram', str(ram),
                        '--receipt', str(out/f'{name}.json')], check=True, capture_output=True, timeout=30)
        memory = ram.read_bytes()
        expected = bytes(131072-expected_nonzero) + bytes([0xA5])*expected_nonzero
        if memory != expected:
            raise RuntimeError(f'Full WRAM byte oracle failed for {name}')
        results.append(dict(variant=name, passed=True, remaining_poison_bytes=expected_nonzero,
                            rom_sha256=hashlib.sha256(rom).hexdigest(),
                            ram_sha256=hashlib.sha256(memory).hexdigest()))
    report = dict(schema='rcr-wram-clear-v1', variants=results,
                  source_sha256=hashlib.sha256((ROOT/'snes/wram_clear.inc').read_bytes()).hexdigest(),
                  core_sha256=hashlib.sha256(core.read_bytes()).hexdigest(),
                  scope='Exact full-memory reset clearing and two incomplete-transfer controls; not gameplay fidelity')
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--core', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    check(args.core, args.out)
