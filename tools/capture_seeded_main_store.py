"""Main-loop observer with an explicit, receipt-bound preloaded SRAM seed."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from tools.audio_packet_log import labels
from tools.benchmark_report import sha
from tools.run_seeded_sram import seed_bytes


def capture(candidate, core, seed, out):
    trace = out.with_name(out.name + '.csv')
    seeded = out.with_name(out.name + '-seed.json')
    if any(p.exists() for p in (out, trace, seeded)):
        raise ValueError('Need fresh capture, trace and seed receipt')
    if seed.read_bytes() != seed_bytes():
        raise ValueError('Need exact empty diagnostic SRAM seed')
    rom = candidate / 'native-cpu.sfc'
    symbols = labels(candidate / 'native_runtime.lbl')
    points = {0: symbols['gameplay_iteration_start'], 1: 0xf282,
              2: symbols['camera_deferred_nmi_exit'] + 2, 3: 0xf2da}
    if rom.read_bytes()[0x10000 + points[2]:0x10002 + points[2]] != bytes.fromhex('85f6'):
        raise ValueError('Unexpected camera store')
    paths = (Path(__file__), Path('tools/run_seeded_sram.py'), Path('tools/run_seeded_benchmark.py'),
             Path('tools/snes9x_main_store.inc'), Path('.deps/snes9x/cpuexec.cpp'),
             Path('tools/benchmark_capture.py'), Path('tools/smoke_libretro.py'),
             candidate / 'native_runtime.lbl', rom, core, seed)
    sources = {str(p): sha(p) for p in paths}
    env = os.environ.copy()
    if any(k.startswith('RCR_MAIN_STORE_') for k in env):
        raise ValueError('Preexisting main observer options')
    env['RCR_MAIN_STORE_TRACE'] = str(trace.resolve())
    for index, pc in points.items():
        env[f'RCR_MAIN_STORE_PC{index}'] = f'{pc:04x}'
    subprocess.run([sys.executable, '-m', 'tools.run_seeded_benchmark', '--seed', str(seed),
        '--receipt', str(seeded), '--', '--system', 'snes',
        '--core', str(core), '--rom', str(rom), '--title', 'build/reference-title-05',
        '--walk', 'build/reference-walk-02', '--scenario', 'traversal-park-single-sweep',
        '--frame-images', '--full-ram-telemetry', '--out', str(out)], env=env, check=True)
    for path, digest in sources.items():
        if sha(Path(path)) != digest:
            raise ValueError('Changed source: ' + path)
    seed_receipt = json.loads(seeded.read_text())
    if seed_receipt['seed_sha256'] != sha(seed) or seed_receipt['loaded'] != [dict(
            rom=str(rom.resolve()), rom_sha256=sha(rom), core=str(core.resolve()), core_sha256=sha(core))]:
        raise ValueError('Seed loaded into a different cartridge/core')
    if not trace.stat().st_size:
        raise ValueError('Missing main observer trace')
    receipt_path = out / 'capture.json'
    receipt = json.loads(receipt_path.read_text())
    receipt['main_store_observer'] = dict(
        sources={**sources, str(seeded): sha(seeded)},
        points={str(k): f'{v:04x}' for k, v in points.items()},
        trace=dict(path=str(trace.resolve()), sha256=sha(trace)),
        scope='Host-only main/input/camera/finish observations. Explicit preloaded SRAM '
              'setup is separately bound; no CPU or WRAM patch or skipped frame.')
    receipt_path.write_text(json.dumps(receipt, indent=2) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('candidate', 'core', 'seed', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    capture(**vars(parser.parse_args()))
