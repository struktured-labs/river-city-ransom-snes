"""Execute CHR read-cache mapping coverage and real-cartridge negative controls."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import struct
import subprocess
import sys

from tools.benchmark_report import sha
from tools.build_runtime_test import build


def patch_runtime(image, address, before, after):
    """Patch every replicated runtime; refuse unexpected bytes or width changes."""
    if len(before) != len(after) or not 0x2000 <= address < 0x6000:
        raise ValueError('Invalid runtime mutation')
    result = bytearray(image)
    for bank in range(1, 9):
        offset = bank * 65536 + address
        if result[offset:offset+len(before)] != before:
            raise ValueError('Mutation preimage mismatch')
        result[offset:offset+len(after)] = after
    result[0xffdc:0xffe0] = b'\xff\xff\0\0'
    checksum = sum(result) & 65535
    struct.pack_into('<HH', result, 0xffdc, checksum ^ 65535, checksum)
    return result


def execute(core, rom, folder, expected_failure=None):
    command = [sys.executable, 'tools/smoke_libretro.py', '--core', str(core),
               '--kind', 'adapter', '--frames', '300', '--rom', str(rom),
               '--ram', str(folder/'memory.ram'), '--receipt', str(folder/'receipt.json')]
    result = subprocess.run(command, capture_output=True, text=True, timeout=45)
    log = folder/'execution.log'
    log.write_text(result.stdout+result.stderr)
    ram = folder/'memory.ram'
    if expected_failure is None:
        if result.returncode:
            raise ValueError(f'Positive adapter failed: {folder}')
    elif result.returncode == 0 or not ram.exists() or ram.read_bytes()[0x1c61] != expected_failure:
        raise ValueError(f'Mutant not rejected in case {expected_failure}: {folder}')
    files = [rom, ram, log]
    if expected_failure is None:
        files.append(folder/'receipt.json')
    return dict(exit_code=result.returncode, expected_failure=expected_failure,
                artifacts={str(p): sha(p) for p in files})


def run(core, out, jobs=4, read_pair=False):
    out.mkdir(parents=True, exist_ok=False)
    sources = [Path(__file__), Path('tools/build_runtime_test.py'), Path('tools/build_native.py'),
               Path('tools/smoke_libretro.py'), Path('snes/runtime_test.asm'),
               Path('snes/native_runtime.asm'), Path('snes/native_runtime.cfg'),
               Path('snes/native_boot.cfg'), Path('snes/bank_restore.inc'),
               Path('.deps/cc65/bin/ca65'), Path('.deps/cc65/bin/ld65'), core]
    sources += sorted(Path('snes').glob('*.inc'))
    bindings = {str(p): sha(p) for p in sources}

    def positive(case):
        enabled, high, mode = case
        folder = out/f'cache-{int(enabled)}-page-{high:02x}-mode-{mode:02x}'
        build(folder, chr_read_cache=enabled, chr_test_high=high, chr_test_mode=mode,
              bank_restore=True, fill_dirty_batch=True, fastrom=True, chr_read_pair=read_pair)
        result = execute(core, folder/'adapter-test.sfc', folder)
        result.update(cache=enabled, page=high, mode=mode)
        return result

    cases = [(enabled, high, mode) for enabled in (False, True)
             for high in range(32) for mode in (0, 128)]
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        positives = list(pool.map(positive, cases))

    # Mode 80/page 00 and mode 00/page 10 expose different mappings on the
    # selector-only and optimized paired-bank operations, without changing data.
    specs = [
        ('generic-invalidation', 0, 128, 'mapper_write', 0, bytes.fromhex('9c501b'), b'\xea'*3),
        ('paired-bank-invalidation', 16, 0, 'bank_switch_enter', 3, bytes.fromhex('9c501b'), b'\xea'*3),
        ('restore-invalidation', 16, 0, 'native_bank_restore', 3, bytes.fromhex('9c501b'), b'\xea'*3),
    ]
    mutants = []
    for name in ('page-key', 'valid-bit', 'pointer-high'):
        specs.append((name, 0, 128, 'chr_read_pointer', None, None, None))
    for name, high, mode, label, delta, before, after in specs:
        base = out/f'cache-1-page-{high:02x}-mode-{mode:02x}'
        labels = {line.split()[2].lstrip('.'): int(line.split()[1], 16)
                  for line in (base/'runtime.lbl').read_text().splitlines()}
        image = (base/'adapter-test.sfc').read_bytes()
        address = labels[label]
        if delta is None:
            patterns = {'page-key': (bytes.fromhex('cd511bd0'), 3, 2),
                        'valid-bit': (bytes.fromhex('ad501bf0'), 3, 2),
                        'pointer-high': (bytes.fromhex('ad551b8501'), 0, 3)}
            pattern, skip, size = patterns[name]
            region = image[65536+address:65536+address+80]
            if region.count(pattern) != 1:
                raise ValueError('Nonunique cache mutation pattern')
            delta = region.index(pattern)+skip
            before = region[delta:delta+size]
            after = bytes.fromhex('ad511b') if name == 'pointer-high' else b'\xea'*size
        folder = out/name
        folder.mkdir()
        rom = folder/'mutant.sfc'
        rom.write_bytes(patch_runtime(image, address+delta, before, after))
        # Generic reads now copy from the shared persistent pointer even on a
        # miss. Both invalid validity and wrong pointer-high are therefore
        # caught by the initial buffered read (case2), before matrix case13.
        result = execute(core, rom, folder, expected_failure=2 if name in ('valid-bit','pointer-high') else 13)
        result.update(name=name, page=high, mode=mode, address=address+delta,
                      before=before.hex(), after=after.hex())
        mutants.append(result)
    if bindings != {str(p): sha(p) for p in sources}:
        raise ValueError('Inputs changed during execution')
    report = dict(passed=True, read_pair=read_pair, positive_cartridges=len(positives), positives=positives,
                  mutants=mutants, sources=bindings,
                  scope='Real adapter suite, cache off/on, all 32 PPU high pages, both mapper '
                  'inversion modes and all 256 values of the selected CHR register. Each value '
                  'checks repeated same-address buffered reads, an adjacent page, selector-only inversion, paired-bank '
                  'entry and bank restoration against independent assembly expectations. '
                  'Four executed mutants fail case13; validity and pointer-high mutants fail '
                  'the initial buffered read in case2. Does not prove decimal-mode or '
                  'interrupt-interleaving equivalence, gameplay speed, or acoustic quality.')
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(dict(passed=True, positive_cartridges=len(positives), rejected_mutants=len(mutants))))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('core', 'out'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--jobs', type=int, choices=range(1, 9), default=4)
    parser.add_argument('--read-pair', action='store_true')
    run(**vars(parser.parse_args()))
