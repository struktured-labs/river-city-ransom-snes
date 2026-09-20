"""Execute scalar/word page-fill adapter tests and reject a missing interior word."""
import argparse
import json
from pathlib import Path
import struct
import subprocess
import sys
from tools.build_runtime_test import build
from tools.benchmark_report import sha


def run(core, out):
    out.mkdir(parents=True, exist_ok=False)
    results = []
    for enabled in (False, True):
        folder = out/('word' if enabled else 'scalar')
        build(folder, word_fill=enabled, fill_dirty_batch=True, fastrom=True)
        command = [sys.executable, 'tools/smoke_libretro.py', '--core', str(core), '--kind', 'adapter',
                   '--frames', '300', '--rom', str(folder/'adapter-test.sfc'),
                   '--ram', str(folder/'memory.ram'), '--receipt', str(folder/'receipt.json')]
        result = subprocess.run(command, capture_output=True, text=True, timeout=30)
        (folder/'execution.log').write_text(result.stdout+result.stderr)
        if result.returncode:
            raise ValueError('Positive adapter execution failed')
        results.append(dict(word_fill=enabled, rom_sha256=sha(folder/'adapter-test.sfc'),
            receipt_sha256=sha(folder/'receipt.json'), ram_sha256=sha(folder/'memory.ram')))
    folder = out/'word'
    runtime = (folder/'runtime.bin').read_bytes()
    pattern = bytes.fromhex('9700c8c8')*8
    if runtime.count(pattern) != 1:
        raise ValueError('Unrolled page-fill sequence not unique')
    offset = 0x2000+runtime.index(pattern)+7*4
    mutant = bytearray((folder/'adapter-test.sfc').read_bytes())
    for bank in range(1, 9):
        mutant[bank*65536+offset:bank*65536+offset+2] = b'\xea\xea'
    mutant[0xffdc:0xffe0] = b'\xff\xff\0\0'
    checksum = sum(mutant) & 65535
    struct.pack_into('<HH', mutant, 0xffdc, checksum ^ 65535, checksum)
    (out/'missing-interior-word.sfc').write_bytes(mutant)
    result = subprocess.run([sys.executable, 'tools/smoke_libretro.py', '--core', str(core),
        '--kind', 'adapter', '--frames', '300', '--rom', str(out/'missing-interior-word.sfc'),
        '--ram', str(out/'mutant.ram'), '--receipt', str(out/'mutant.json')],
        capture_output=True, text=True, timeout=30)
    (out/'mutant.log').write_text(result.stdout+result.stderr)
    ram = (out/'mutant.ram').read_bytes()
    if result.returncode == 0 or ram[0x1c61] != 16:
        raise ValueError('Missing word did not fail the page-fill case')
    report = dict(passed=True, positive_arms=results, rejected_mutant_case=16,
        mutant_exit_code=result.returncode,
        core_sha256=sha(core),
        sources={str(p): sha(p) for p in (Path(__file__), Path('tools/build_runtime_test.py'),
            Path('snes/runtime_test.asm'), Path('snes/native_runtime.asm'), out/'missing-interior-word.sfc',
            out/'mutant.ram', out/'mutant.log')},
        scope='Existing real adapter suite in both modes. Case 16 checks all bytes of an attribute '
        'page, four aligned pages, zero-as-256 page count, wrapping, dirty flags and return state. '
        'Missing eighth word of every group is rejected. Not all possible input states or game speed.')
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(dict(passed=True, rejected_mutant_case=16)))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('core', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    run(**vars(p.parse_args()))
