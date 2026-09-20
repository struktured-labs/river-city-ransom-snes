"""Fresh-process, observer-only DSP sample/command timing capture."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from tools.benchmark_report import sha

SOURCES = ('tools/capture_dsp_latency.py','tools/snes9x_dsp_latency.inc',
    'tools/benchmark_capture.py','tools/smoke_libretro.py',
    '.deps/snes9x/apu/apu.cpp','.deps/snes9x/apu/bapu/smp/core.cpp',
    '.deps/snes9x/apu/bapu/dsp/SPC_DSP.h','.deps/snes9x/apu/bapu/dsp/SPC_DSP.cpp',
    '.deps/snes9x/apu/resampler.h')


def capture(core, rom, out):
    if out.exists(): raise ValueError('Use a fresh capture directory')
    sources={p:sha(Path(p)) for p in SOURCES}
    traces={name:out.with_name(out.name+suffix) for name,suffix in (
        ('RCR_DSP_LATENCY_TRACE','-dsp.csv'),('RCR_DSP_DAC_PCM','-dac.pcm'),
        ('RCR_SPC_SYNTH_TRACE','-synth.csv'),('RCR_SPC_GAME_KEYON_TRACE','-keyon.csv'),
        ('RCR_SPC_RECEIVE_TRACE','-received.csv'),('RCR_AUDIO_BUS_TRACE','-bus.csv'))}
    if any(p.exists() for p in traces.values()): raise ValueError('Trace path already exists')
    env=os.environ.copy();env.update({k:str(v.resolve()) for k,v in traces.items()})
    subprocess.run([sys.executable,'tools/benchmark_capture.py','--system','snes',
        '--core',str(core),'--rom',str(rom),'--title','build/reference-title-05',
        '--walk','build/reference-walk-02','--scenario','traversal-park-single-sweep',
        '--frame-images','--full-ram-telemetry','--out',str(out)],env=env,check=True)
    for p,h in sources.items():
        if sha(Path(p))!=h: raise ValueError('Observer source changed during capture: '+p)
    if any(not p.is_file() or not p.stat().st_size for p in traces.values()):
        raise ValueError('Missing or empty observer output')
    receipt_path=out/'capture.json';receipt=json.loads(receipt_path.read_text())
    receipt['dsp_latency_observer']=dict(sources=sources,
        traces={k:dict(path=str(p.resolve()),sha256=sha(p)) for k,p in traces.items()},
        scope='Fresh-process observer. DSP write sample indices are after existing synchronization; '
              'packet/ready sample indices may lag pending DSP clocks (logged explicitly). '
              'Raw DAC is pre-resampler. No emulated synchronization or audio changes added.')
    receipt_path.write_text(json.dumps(receipt,indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('core','rom','out'):p.add_argument('--'+name,type=Path,required=True)
    capture(**vars(p.parse_args()))
