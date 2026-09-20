"""Neutral full-game DSP startup and original main-loop observation."""
import argparse
import json
import os
from pathlib import Path

from tools.benchmark_report import sha, verify_capture
from tools.capture_combat_instructions import equivalent
from tools.capture_dsp_latency import capture as capture_dsp


def capture(candidate, core, normal, out):
    if out.exists() or any(k.startswith('RCR_') for k in os.environ):
        raise ValueError('Fresh output and clean observer environment required')
    baseline, previous = verify_capture(normal)
    if baseline['core_sha256'] != sha(core) or baseline['rom_sha256'] != sha(candidate/'native-cpu.sfc'):
        raise ValueError('Different same-core game control')
    labels = candidate/'native_runtime.lbl'
    syms = {s.split()[2].lstrip('.'): int(s.split()[1], 16) for s in labels.read_text().splitlines()}
    points = {0: syms['gameplay_iteration_start'], 1: 0xf282,
              2: syms['camera_deferred_nmi_exit']+2, 3: 0xf2da}
    image = (candidate/'native-cpu.sfc').read_bytes()
    if image[0x10000+points[2]:0x10000+points[2]+2] != bytes.fromhex('85f6'):
        raise ValueError('Changed pre-STA camera site')
    onset = out.with_name(out.name+'-onset.csv')
    main = out.with_name(out.name+'-main.csv')
    if onset.exists() or main.exists():
        raise ValueError('Fresh traces required')
    paths = [Path(__file__), Path('tools/capture_dsp_latency.py'), Path('tools/capture_combat_instructions.py'),
             Path('tools/snes9x_pulse_onset.inc'), Path('tools/snes9x_dsp_latency.inc'),
             Path('tools/snes9x_main_store.inc'), core, labels, candidate/'manifest.json',
             candidate/'native-cpu.sfc', normal/'capture.json']
    paths += [core.parent.parent/p for p in ('cpuexec.cpp', 'apu/bapu/dsp/SPC_DSP.cpp',
                                            'apu/bapu/dsp/SPC_DSP.h', 'apu/bapu/smp/core.cpp', 'apu/apu.cpp')]
    sources = {str(p): sha(p) for p in paths}
    env = dict(RCR_MAIN_STORE_TRACE=str(main.resolve()), RCR_PULSE_ONSET_TRACE=str(onset.resolve()))
    env.update({f'RCR_MAIN_STORE_PC{k}': f'{v:04x}' for k, v in points.items()})
    try:
        os.environ.update(env)
        capture_dsp(core, candidate/'native-cpu.sfc', out)
    finally:
        for k in env:
            os.environ.pop(k, None)
    receipt, rows = verify_capture(out)
    equivalent(receipt, rows, baseline, previous)
    if any(sha(p) != h for p, h in sources.items()) or not onset.stat().st_size or not main.stat().st_size:
        raise ValueError('Changed source or empty trace')
    sources.update({str(p): sha(p) for p in (main, onset)})
    receipt['main_store_observer'] = dict(sources=sources, points={str(k): f'{v:04x}' for k, v in points.items()},
        trace=dict(path=str(main), sha256=sha(main)))
    (out/'capture.json').write_text(json.dumps(receipt, indent=2)+'\n')
    sources[str(out/'capture.json')] = sha(out/'capture.json')
    (out/'startup-game.json').write_text(json.dumps(dict(sources=sources, onset=str(onset), main=str(main),
        points={str(k): v for k, v in points.items()}, observer_neutral=True, frames=len(rows), scope=__doc__), indent=2)+'\n')
    print(json.dumps(dict(observer_neutral=True, frames=len(rows))))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('candidate', 'core', 'normal', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    capture(**vars(p.parse_args()))
