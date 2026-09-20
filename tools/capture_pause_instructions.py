"""Observe a bounded pause instruction window with full same-core PCM neutrality."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from tools.benchmark_report import sha, verify_capture
from tools.capture_combat_instructions import equivalent


def capture(core, rom, normal, out, first, last):
    if out.exists() or any(k.startswith('RCR_') for k in os.environ):
        raise ValueError('Fresh output and clean observer environment required')
    baseline, control = verify_capture(normal)
    if (baseline['system'] != 'snes' or baseline['scenario_name'] != 'pause-status'
            or baseline['core_sha256'] != sha(core) or not 1 <= first <= last <= baseline['frames']):
        raise ValueError('Need matching pause control and bounded window')
    if sha(rom) != baseline['rom_sha256']:
        raise ValueError('Changed cartridge')
    traces = {key: out.with_name(out.name + suffix) for key, suffix in (
        ('RCR_INSTRUCTION_TRACE', '-instructions.csv'),
        ('RCR_DSP_LATENCY_TRACE', '-dsp.csv'),
        ('RCR_SPC_RECEIVE_TRACE', '-received.csv'),
        ('RCR_AUDIO_BUS_TRACE', '-bus.csv'))}
    binary = core.read_bytes()
    if any(p.exists() or key.encode() not in binary for key, p in traces.items()):
        raise ValueError('Trace already exists or observer absent')
    paths = [Path(__file__), Path('tools/benchmark_report.py'),
        Path('tools/capture_combat_instructions.py'), Path('tools/benchmark_capture.py'),
        Path('tools/smoke_libretro.py'), Path('tools/snes9x_instruction_trace.inc'),
        core, rom, normal/'capture.json', normal/'timeline.json', normal/'audio.wav']
    sources = {str(p): sha(p) for p in paths}
    env = dict(os.environ, RCR_PROFILE_FIRST=str(first), RCR_PROFILE_LAST=str(last))
    env.update({key: str(p.resolve()) for key, p in traces.items()})
    started = time.monotonic()
    subprocess.run([sys.executable, '-m', 'tools.benchmark_capture', '--system', 'snes',
        '--core', str(core), '--rom', str(rom), '--title', 'build/reference-title-05',
        '--walk', 'build/reference-walk-02', '--scenario', 'pause-status',
        '--frame-images', '--full-ram-telemetry', '--out', str(out)], env=env, check=True)
    elapsed = time.monotonic()-started
    receipt, rows = verify_capture(out)
    equivalent(receipt, rows, baseline, control)
    if any(not p.is_file() or not p.stat().st_size for p in traces.values()):
        raise ValueError('Missing trace')
    if any(sha(Path(p)) != h for p, h in sources.items()):
        raise ValueError('Changed source during capture')
    sources.update({str(p): sha(p) for p in [*traces.values(),
        out/'capture.json', out/'timeline.json', out/'audio.wav']})
    report = dict(observer_neutral=True, first=first, last=last, frames=len(rows),
        capture_wall_seconds=elapsed, sources=sources,
        traces={key: str(p) for key, p in traces.items()},
        scope=__doc__+' Host-only instruction-entry trace; clocks include DMA/events. '
        'No input, emulated state, sound commands, or samples edited.')
    (out/'pause-observer.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('sources','traces')}))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('core', 'rom', 'normal', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    for name in ('first', 'last'):
        p.add_argument('--'+name, type=int, required=True)
    capture(**vars(p.parse_args()))
