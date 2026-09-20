"""Bounded CPU trace around late audio service, with full-route neutrality."""
import argparse
import json
import os
from pathlib import Path
import time
from tools.benchmark_report import sha, verify_capture
from tools.capture_combat_instructions import equivalent
from tools.capture_dsp_latency import capture as capture_dsp


def capture(candidate, core, normal, out, first, last):
    trace = out.with_name(out.name + '-instructions.csv')
    if out.exists() or trace.exists() or any(k.startswith('RCR_') for k in os.environ):
        raise ValueError('Fresh paths and clean observer environment required')
    baseline, previous = verify_capture(normal)
    rom = candidate / 'native-cpu.sfc'
    if (baseline['core_sha256'] != sha(core) or baseline['rom_sha256'] != sha(rom)
            or baseline['scenario_name'] != 'traversal-park-single-sweep'
            or not 1 <= first <= last <= baseline['frames']):
        raise ValueError('Wrong control or instruction window')
    paths = [Path(__file__), Path('tools/capture_dsp_latency.py'),
             Path('tools/capture_combat_instructions.py'), Path('tools/benchmark_report.py'),
             Path('tools/snes9x_instruction_trace.inc'), core.parent.parent / 'cpuexec.cpp',
             core, rom, normal / 'capture.json']
    sources = {str(p): sha(p) for p in paths}
    env = dict(RCR_INSTRUCTION_TRACE=str(trace.resolve()), RCR_PROFILE_FIRST=str(first),
               RCR_PROFILE_LAST=str(last))
    started = time.monotonic()
    try:
        os.environ.update(env)
        capture_dsp(core, rom, out)
    finally:
        for key in env:
            os.environ.pop(key, None)
    elapsed = time.monotonic() - started
    receipt, rows = verify_capture(out)
    equivalent(receipt, rows, baseline, previous)
    if not trace.stat().st_size or any(sha(p) != h for p, h in sources.items()):
        raise ValueError('Changed source or missing trace')
    sources.update({str(p): sha(p) for p in (trace, out / 'capture.json')})
    report = dict(sources=sources, observer_neutral=True, first=first, last=last,
                  frames=len(rows), trace=str(trace), replay_seconds=elapsed, scope=__doc__)
    (out / 'service-instructions.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ('frames', 'observer_neutral', 'replay_seconds')}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('candidate', 'core', 'normal', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    for name in ('first', 'last'):
        parser.add_argument('--' + name, type=int, required=True)
    capture(**vars(parser.parse_args()))
