"""Read-only complete DSP pulse-pitch trace alongside existing startup evidence."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from tools.benchmark_report import sha


def capture(core,fixture,out):
    tree=core.parent.parent
    paths=[Path(__file__),Path('tools/snes9x_pulse_pitch.inc'),Path('tools/snes9x_pulse_onset.inc'),
        Path('tools/snes9x_dsp_latency.inc'),Path('tools/replay_spc_packets.py'),Path('tools/smoke_libretro.py'),
        core,fixture/'manifest.json',fixture/'player.sfc',tree/'apu/bapu/dsp/SPC_DSP.cpp',
        tree/'apu/bapu/dsp/SPC_DSP.h',tree/'apu/bapu/smp/core.cpp',tree/'apu/apu.cpp']
    sources={str(p):sha(p) for p in paths}
    traces={k:out.with_name(out.name+suffix) for k,suffix in (
        ('RCR_PULSE_PITCH_TRACE','-pitch.csv'),('RCR_PULSE_ONSET_TRACE','-voice.csv'),
        ('RCR_DSP_LATENCY_TRACE','-dsp.csv'),('RCR_DSP_DAC_PCM','-dac.pcm'),
        ('RCR_SPC_RECEIVE_TRACE','-received.csv'))}
    if out.exists() or any(p.exists() for p in traces.values()):raise ValueError('Need fresh outputs')
    if any(k.startswith(('RCR_DSP_','RCR_SPC_','RCR_PULSE_')) for k in os.environ):
        raise ValueError('Unexpected inherited observer options')
    env=dict(os.environ,**{k:str(p.resolve()) for k,p in traces.items()})
    subprocess.run([sys.executable,'-m','tools.replay_spc_packets','execute','--core',str(core),
        '--fixture',str(fixture),'--out',str(out)],env=env,check=True)
    if sources!={str(p):sha(p) for p in paths}:raise ValueError('Changed observer sources')
    if any(not p.stat().st_size for p in traces.values()):raise ValueError('Missing observer trace')
    sources.update({str(p):sha(p) for p in traces.values()})
    sources[str(out/'report.json')]=sha(out/'report.json')
    # The existing startup loader validates full neutral PCM/RAM/timeline,
    # received packet bytes, raw DAC and DSP clocks before pitch analysis.
    (out/'onset-observer.json').write_text(json.dumps(dict(sources=sources,
        traces={k:str(p) for k,p in traces.items()},scope=__doc__),indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('core','fixture','out'):p.add_argument('--'+name,type=Path,required=True)
    capture(**vars(p.parse_args()))
