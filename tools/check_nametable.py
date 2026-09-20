"""Execute CPU-side MMC3 nametable alias checks (currently an open fidelity gate)."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

try:
    from .build_runtime_test import build, ROOT
except ImportError:
    from build_runtime_test import build, ROOT


def check(core, out):
    results = []
    for mode, label in ((0, 'vertical'), (1, 'horizontal')):
        directory = out / label
        build(directory, nametable_mode=mode)
        rom = directory / 'adapter-test.sfc'
        run = subprocess.run([
            sys.executable, str(ROOT/'tools/smoke_libretro.py'),
            '--core', str(core), '--rom', str(rom), '--kind', 'adapter',
            '--frames', '300', '--receipt', str(directory/'receipt.json'),
        ], capture_output=True, text=True, timeout=30)
        (directory/'stdout.log').write_text(run.stdout)
        (directory/'stderr.log').write_text(run.stderr)
        negative_passed = False
        if run.returncode == 0:
            image = rom.read_bytes()
            good, bad = (
                (bytes.fromhex('a5012927850160'), bytes.fromhex('a501292f850160'))
                if mode == 0 else
                (bytes.fromhex('a5014a29040503850160'), bytes.fromhex('a501ea29040503850160'))
            )
            if image.count(good) != 8:
                raise RuntimeError('Cannot identify one mirroring control per bank')
            mutant = directory/'wrong-mirroring.sfc'
            mutant.write_bytes(image.replace(good, bad))
            negative = subprocess.run([
                sys.executable, str(ROOT/'tools/smoke_libretro.py'),
                '--core', str(core), '--rom', str(mutant), '--kind', 'adapter',
                '--frames', '300',
            ], capture_output=True, text=True, timeout=30)
            (directory/'negative-stderr.log').write_text(negative.stderr)
            negative_passed = negative.returncode != 0 and f'WRAM status=ee, adapter case={22+mode}' in negative.stderr
        results.append(dict(mode=label, passed=run.returncode == 0,
                            negative_control_passed=negative_passed,
                            returncode=run.returncode, assertion_case=22+mode,
                            rom_sha256=hashlib.sha256(rom.read_bytes()).hexdigest()))
    report = dict(schema='rcr-nametable-cpu-gate-v1',
                  scope='CPU writes and buffered reads at one offset across four logical tables, live mapping changes, row invalidation, and A001 isolation; not full renderer certification',
                  core_sha256=hashlib.sha256(core.read_bytes()).hexdigest(),
                  gates=results, passed=all(r['passed'] and r['negative_control_passed'] for r in results))
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))
    return report['passed']


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--core', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    sys.exit(0 if check(args.core, args.out) else 1)
