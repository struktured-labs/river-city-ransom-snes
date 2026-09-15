"""Positive and corrupted-CHR negative controls of real SNES adapter execution."""
import argparse
from pathlib import Path
import subprocess
import sys

try:
    from .build_runtime_test import build, ROOT
except ImportError:
    from build_runtime_test import build, ROOT


def check(core):
    out = ROOT / "build/runtime-test"
    build(out)
    command = [sys.executable, str(ROOT / "tools/smoke_libretro.py"), "--core", str(core),
               "--kind", "adapter", "--frames", "300"]
    subprocess.run(command + ["--rom", str(out / "adapter-test.sfc"),
                               "--receipt", str(out / "receipt.json")], check=True, timeout=30)
    # Preserve the valid cartridge; deliberately corrupt only a separate fixture.
    bad = bytearray((out / "adapter-test.sfc").read_bytes())
    bad[0xF0000 + 0x42 * 1024 + 0x15] ^= 1
    negative = out / "corrupted-chr.sfc"
    negative.write_bytes(bad)
    result = subprocess.run(command + ["--rom", str(negative)], capture_output=True, text=True, timeout=30)
    if not result.returncode or "WRAM status=ee, adapter case=2" not in result.stderr:
        raise RuntimeError("Corrupted CHR did not fail the expected executed adapter assertion")
    print("Adapter positive control passed; corrupted-CHR negative control failed at the expected assertion.")
    controls = ROOT / "build/controller-test"
    build(controls, controllers=True)
    control_cmd = command + ["--rom", str(controls / "adapter-test.sfc")]
    subprocess.run(control_cmd + ["--profile", "select-control", "--receipt", str(controls / "receipt.json")],
                   check=True, timeout=30)
    missing = subprocess.run(control_cmd, capture_output=True, text=True, timeout=30)
    if not missing.returncode or "WRAM status=ee, adapter case=5" not in missing.stderr:
        raise RuntimeError("Missing Select input did not fail the controller assertion")
    print("P1 Select/P2 Start serial routing passed; absent-input negative control failed correctly.")
    jump = ROOT / 'build/jump-test'
    build(jump, jump=True)
    jump_cmd = command + ['--rom', str(jump/'adapter-test.sfc')]
    for profile in ('jump-control', 'jump-swapped'):
        subprocess.run(jump_cmd + ['--profile', profile, '--receipt', str(jump/(profile+'.json'))], check=True, timeout=30)
    missing = subprocess.run(jump_cmd, capture_output=True, text=True, timeout=30)
    if not missing.returncode or 'WRAM status=ee, adapter case=5' not in missing.stderr:
        raise RuntimeError('Absent jump buttons did not fail the executed assertion')
    print('SNES A and B+Y produce identical NES A+B on both ports; absent-input control fails.')


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core", type=Path, required=True)
    check(parser.parse_args().core)
