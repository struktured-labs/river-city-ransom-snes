"""Execute four-page dirty batching and a truncated-row negative control."""
import argparse
from pathlib import Path
import subprocess
import sys

try:
    from .build_runtime_test import build, ROOT
except ImportError:
    from build_runtime_test import build, ROOT


def run(core, rom, expect=None):
    command = [sys.executable, str(ROOT / 'tools/smoke_libretro.py'), '--core', str(core),
               '--kind', 'adapter', '--frames', '300', '--rom', str(rom)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=30)
    if expect is None and result.returncode:
        raise RuntimeError(result.stderr or result.stdout)
    if expect is not None and (not result.returncode or expect not in result.stderr):
        raise RuntimeError(f'Fill batching mutation did not fail with {expect}: {result.stderr}')


def check(core):
    out = ROOT / 'build/runtime-fill-dirty-batch'
    build(out, fill_dirty_batch=True)
    good = out / 'adapter-test.sfc'
    run(core, good)
    image = good.read_bytes()
    symbols = {line.split()[2].lstrip('.'): int(line.split()[1], 16)
               for line in (out / 'runtime.lbl').read_text().splitlines()}
    rows = bytes.fromhex('a02020') + symbols['dirty_mirrored_row'].to_bytes(2, 'little')
    if image.count(rows) != 8:
        raise RuntimeError('Expected one complete-table dirty loop per runtime bank')
    bad = out / 'missing-final-row.sfc'
    bad.write_bytes(image.replace(rows, bytes.fromhex('a01f20') + rows[3:]))
    run(core, bad, 'WRAM status=ee, adapter case=16')
    print('Four-page fill data/flags/ABI pass; omitting the final row fails executed case 16.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--core', type=Path, required=True)
    args = parser.parse_args()
    check(args.core)
