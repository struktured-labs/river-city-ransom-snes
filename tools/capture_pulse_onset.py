"""Fresh-process read-only DSP voice startup observation during fixed packet replay."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from tools.benchmark_report import sha


def capture(core, fixture, out):
    if out.exists():
        raise ValueError('Use new outputs')
    if any(k.startswith(('RCR_DSP_', 'RCR_SPC_', 'RCR_PULSE_')) for k in os.environ):
        raise ValueError('Unexpected inherited observer configuration')
    tree = core.parent.parent
    paths = [Path(__file__), Path('tools/snes9x_pulse_onset.inc'),
        Path('tools/snes9x_dsp_latency.inc'), Path('tools/replay_spc_packets.py'),
        Path('tools/smoke_libretro.py'), core, fixture/'manifest.json', fixture/'player.sfc',
        tree/'apu/bapu/dsp/SPC_DSP.cpp', tree/'apu/bapu/dsp/SPC_DSP.h',
        tree/'apu/bapu/smp/core.cpp', tree/'apu/apu.cpp']
    sources = {str(p): sha(p) for p in paths}
    traces = {key: out.with_name(out.name+suffix) for key, suffix in [
        ('RCR_PULSE_ONSET_TRACE', '-voice.csv'), ('RCR_DSP_LATENCY_TRACE', '-dsp.csv'),
        ('RCR_DSP_DAC_PCM', '-dac.pcm'), ('RCR_SPC_RECEIVE_TRACE', '-received.csv')]}
    if any(p.exists() for p in traces.values()):
        raise ValueError('Trace output already exists')
    env = os.environ.copy()
    env.update({k: str(v.resolve()) for k, v in traces.items()})
    subprocess.run([sys.executable, '-m', 'tools.replay_spc_packets', 'execute',
        '--core', str(core), '--fixture', str(fixture), '--out', str(out)], env=env, check=True)
    if sources != {str(p): sha(p) for p in paths}:
        raise ValueError('Sources changed during capture')
    if any(not p.stat().st_size for p in traces.values()):
        raise ValueError('Empty voice/clock/PCM/receiver trace')
    sources.update({str(p): sha(p) for p in traces.values()})
    sources[str(out/'report.json')] = sha(out/'report.json')
    (out/'onset-observer.json').write_text(json.dumps(dict(sources=sources,
        traces={k: str(v) for k, v in traces.items()}, scope=__doc__), indent=2)+'\n')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('core', 'fixture', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    capture(**vars(p.parse_args()))
