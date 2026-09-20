"""Reproduce a failed camera diagnostic with an optional bounded host trace.

Exact replay of a failure qualifies the observer only, never the cartridge.
"""
import argparse
import json
import os
from pathlib import Path

from tools import benchmark_capture as benchmark
from tools.benchmark_report import sha, verify_capture
from tools.camera_state_log import seed_bytes
from tools.run_seeded_benchmark import seeded_core


def capture(candidate, core, out, control=None, first=1188, last=1202):
    trace = out.with_suffix('.csv')
    if out.exists() or trace.exists() or any(k.startswith('RCR_') for k in os.environ):
        raise ValueError('Fresh process and outputs required')
    if not 1 <= first <= last or b'RCR_INSTRUCTION_TRACE' not in core.read_bytes():
        raise ValueError('Need bounded window and instruction-enabled core')
    rom = candidate/'native-cpu.sfc'
    manifest = candidate/'manifest.json'
    if sha(rom) != json.loads(manifest.read_text())['rom_sha256']:
        raise ValueError('Changed candidate')
    paths = (Path(__file__), Path('tools/benchmark_capture.py'),
             Path('tools/benchmark_report.py'), Path('tools/smoke_libretro.py'),
             Path('tools/run_seeded_benchmark.py'), Path('tools/camera_state_log.py'),
             Path('tools/snes9x_instruction_trace.inc'), core, rom, manifest)
    sources = {str(p): sha(p) for p in paths}
    env = {}
    if control is not None:
        baseline, plain = verify_capture(control)
        env = dict(RCR_INSTRUCTION_TRACE=str(trace.resolve()),
                   RCR_PROFILE_FIRST=str(first), RCR_PROFILE_LAST=str(last))
        for name in ('capture.json', 'timeline.json', 'audio.wav'):
            p = control/name
            sources[str(p)] = sha(p)
    loaded = []
    refs = {'menu': (Path('build/reference-title-05'), 600),
            'settings': (Path('build/reference-walk-02'), 600),
            'story': (Path('build/reference-walk-02'), 900),
            'street': (Path('build/reference-walk-02'), 1800)}
    try:
        os.environ.update(env)
        with seeded_core(core, seed_bytes(), loaded):
            benchmark.capture(core, rom, 'snes', refs, out, 'pause-status', True, True)
    finally:
        for key in env:
            os.environ.pop(key, None)
    receipt, rows = verify_capture(out)
    if loaded != [dict(rom=str(rom.resolve()), rom_sha256=sha(rom),
                       core=str(core.resolve()), core_sha256=sha(core))]:
        raise ValueError('Unexpected seeded load')
    if control is not None:
        for key in ('rom_sha256', 'core_sha256', 'scenario_sha256', 'frames',
                    'audio_sha256', 'capture_complete'):
            if receipt[key] != baseline[key]:
                raise ValueError('Observer changed '+key)
        if rows != plain or not trace.stat().st_size:
            raise ValueError('Observer changed timeline or trace is missing')
        sources[str(trace)] = sha(trace)
    if any(sha(Path(p)) != h for p, h in sources.items()):
        raise ValueError('Sources changed')
    for name in ('capture.json', 'timeline.json', 'audio.wav'):
        p = out/name
        sources[str(p)] = sha(p)
    report = dict(sources=sources, loaded=loaded, observer_neutral=control is not None,
                  capture_complete=receipt['capture_complete'], frames=len(rows),
                  fault_frames=sum(bool(r['fault']) for r in rows),
                  first_fault=next((r['frame'] for r in rows if r['fault']), None),
                  trace=str(trace) if control is not None else None,
                  first=first, last=last, cartridge_qualified=False, scope=__doc__)
    (out/'failure-observer.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k: v for k, v in report.items() if k not in ('sources', 'loaded')}))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('candidate', 'core', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    p.add_argument('--control', type=Path)
    for name, default in (('first', 1188), ('last', 1202)):
        p.add_argument('--'+name, type=int, default=default)
    capture(**vars(p.parse_args()))
