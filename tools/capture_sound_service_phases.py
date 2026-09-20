"""Observe original sound-driver entry/return without changing execution."""
import argparse
import json
import os
from pathlib import Path
import time

from tools.benchmark_report import sha, verify_capture
from tools.capture_combat_instructions import equivalent
from tools.capture_dsp_latency import capture as capture_dsp


def capture(candidate, core, normal, out):
    trace = out.with_name(out.name + '-service.csv')
    if out.exists() or trace.exists() or any(k.startswith('RCR_') for k in os.environ):
        raise ValueError('Fresh paths and clean observer environment required')
    started = time.monotonic()
    baseline, previous = verify_capture(normal)
    rom = candidate / 'native-cpu.sfc'
    if (baseline['rom_sha256'] != sha(rom) or baseline['core_sha256'] != sha(core)
            or baseline['scenario_name'] != 'traversal-park-single-sweep'):
        raise ValueError('Wrong cartridge/core/scenario control')
    image = rom.read_bytes()
    expected = bytes.fromhex('adffbf48a90520d1fe2003806820d1fe60')
    for bank in range(1, 9):
        offset = bank * 65536 + 0xfa54
        if image[offset:offset + len(expected)] != expected:
            raise ValueError('Changed original sound-driver envelope')
    paths = [Path(__file__), Path('tools/capture_dsp_latency.py'),
             Path('tools/capture_combat_instructions.py'), Path('tools/benchmark_report.py'),
             Path('tools/snes9x_main_store.inc'), core.parent.parent / 'cpuexec.cpp',
             core, rom, candidate / 'manifest.json', normal / 'capture.json']
    sources = {str(p): sha(p) for p in paths}
    points = {0: 0xfa54, 1: 0xfa64, 2: 0x5f00, 3: 0x7885}
    env = {'RCR_MAIN_STORE_TRACE': str(trace.resolve())}
    env.update({f'RCR_MAIN_STORE_PC{k}': f'{v:04x}' for k, v in points.items()})
    replay_start = time.monotonic()
    try:
        os.environ.update(env)
        capture_dsp(core, rom, out)
    finally:
        for key in env:
            os.environ.pop(key, None)
    replay_seconds = time.monotonic() - replay_start
    receipt, rows = verify_capture(out)
    equivalent(receipt, rows, baseline, previous)
    if not trace.stat().st_size or any(sha(p) != digest for p, digest in sources.items()):
        raise ValueError('Missing observation or changed source')
    sources[str(trace)] = sha(trace)
    sources[str(out / 'capture.json')] = sha(out / 'capture.json')
    report = dict(sources=sources, trace=str(trace), observer_neutral=True,
                  frames=len(rows), points=points, replay_seconds=replay_seconds,
                  total_seconds=time.monotonic() - started,
                  scope='Full primary timeline/native PCM unchanged. Entry/return clocks '
                        'include interrupts and DMA. Return observed before RTS execution.')
    (out / 'sound-service.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ('frames', 'observer_neutral', 'replay_seconds')}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('candidate', 'core', 'normal', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    capture(**vars(parser.parse_args()))
