"""Execute the guarded constant-fill DMA path and mutation controls."""
import argparse
from pathlib import Path
import subprocess
import sys

try:
    from .build_runtime_test import build, ROOT
except ImportError:
    from build_runtime_test import build, ROOT


def run(core, rom, expect=None):
    command = [sys.executable, str(ROOT / 'tools/smoke_libretro.py'),
               '--core', str(core), '--kind', 'adapter', '--frames', '300',
               '--rom', str(rom)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=30)
    if expect is None:
        if result.returncode:
            raise RuntimeError(result.stderr or result.stdout)
    elif not result.returncode or expect not in result.stderr:
        raise RuntimeError(f'DMA mutation did not fail with {expect}: {result.stderr}')


def check(core):
    out = ROOT / 'build/runtime-rect-dma'
    build(out, rect_dma=True)
    good = out / 'adapter-test.sfc'
    run(core, good)
    image = good.read_bytes()

    fixed = bytes.fromhex('547f7f')
    if image.count(fixed) != 8:
        raise RuntimeError('Expected one overlapping MVN fill per runtime bank')
    path = out / 'wrong-copy-bank.sfc'
    path.write_bytes(image.replace(fixed, bytes.fromhex('547e7f')))
    run(core, path, 'WRAM status=ee, adapter case=26')

    symbols = {line.split()[2].lstrip('.'): int(line.split()[1], 16)
               for line in (out / 'runtime.lbl').read_text().splitlines()}
    mark = b'\x20' + symbols['mark_ppu_dirty'].to_bytes(2, 'little') + bytes.fromhex('ad261c')
    if image.count(mark) != 8:
        raise RuntimeError('Expected one DMA dirty-segment loop per runtime bank')
    path = out / 'missing-dirty-segments.sfc'
    path.write_bytes(image.replace(mark, b'\xea\xea\xea' + mark[3:]))
    run(core, path, 'WRAM status=ee, adapter case=26')
    print('Rectangle block fill passes executed byte/alias/ABI cases; wrong-bank and missing-dirty mutations fail case 26.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--core', type=Path, required=True)
    args = parser.parse_args()
    check(args.core)
