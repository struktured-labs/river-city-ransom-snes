"""Fresh-process neutral sweep-state observation; no fitted audio alignment."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from tools.audit_stimulus_audio import verify_sources
from tools.benchmark_report import sha,verify_capture


def capture(system,normal,core,out,rom=None):
    if out.exists():raise ValueError('Use a fresh output')
    env=os.environ.copy()
    if any(k.startswith('RCR_') for k in env):raise ValueError('Unexpected inherited observer configuration')
    paths=[Path(__file__),core,Path('tools/benchmark_capture.py'),Path('tools/smoke_libretro.py')]
    trace=out.with_name(out.name+'-sweep.csv')
    if trace.exists():raise ValueError('Existing sweep trace')
    if system=='snes':
        if rom is None:raise ValueError('Need game ROM')
        receipt,_=verify_capture(normal)
        if receipt['rom_sha256']!=sha(rom):raise ValueError('Different normal ROM')
        paths += [rom,normal/'capture.json',normal/'timeline.json',normal/'audio.wav',
            Path('tools/snes9x_sweep_trace.inc'),Path('.deps/snes9x-sweep-trace-1071/apu/bapu/smp/core.cpp')]
        bus=out.with_name(out.name+'-bus.csv');received=out.with_name(out.name+'-received.csv')
        if bus.exists() or received.exists():raise ValueError('Existing transport traces')
        env.update(RCR_SPC_SWEEP_TRACE=str(trace.resolve()),RCR_AUDIO_BUS_TRACE=str(bus.resolve()),
                   RCR_SPC_RECEIVE_TRACE=str(received.resolve()))
        command=[sys.executable,'tools/benchmark_capture.py','--system','snes','--core',str(core),
            '--rom',str(rom),'--title','build/reference-title-05','--walk','build/reference-walk-02',
            '--scenario','traversal-park-single-sweep','--frame-images','--full-ram-telemetry','--out',str(out)]
        compare=('timeline.json','audio.wav')
    elif system=='nes':
        if rom is not None:raise ValueError('NES replay supplies its bound ROM')
        receipt=verify_sources(normal/'report.json')
        paths += [normal/'report.json',normal/'player.nes',normal/'stimulus.bin',normal/'timeline.json',
            normal/'audio.wav',normal/'memory.ram',Path('tools/fceumm_sweep_trace.inc'),
            Path('.deps/fceumm-sweep-1071/src/sound.c'),Path('tools/replay_nes_apu_stimulus.py')]
        env['RCR_NES_SWEEP_TRACE']=str(trace.resolve())
        command=[sys.executable,'-m','tools.replay_nes_apu_stimulus','--control-rom',str(normal/'player.nes'),
            '--control-stimulus',str(normal/'stimulus.bin'),'--core',str(core),
            '--frames',str(receipt['source_frames']),'--out',str(out)]
        compare=('timeline.json','audio.wav','memory.ram')
    else:raise ValueError('Unknown system')
    sources={str(p):sha(p) for p in paths}
    subprocess.run(command,env=env,check=True)
    for path,digest in sources.items():
        if sha(Path(path))!=digest:raise ValueError('Source changed during capture: '+path)
    for name in compare:
        if (normal/name).read_bytes()!=(out/name).read_bytes():raise ValueError('Observer changed '+name)
    if not trace.stat().st_size:raise ValueError('Missing sweep trace')
    report=dict(system=system,observer_neutral=True,trace=str(trace),normal=str(normal),
        sources={**sources,**{str(p):sha(p) for p in [trace,*[out/name for name in compare]]}},
        scope='Fresh-process host-only sweep register observations. Complete normal/observer WAV '
        'and timeline equality, plus final RAM for NES. NES source is publication-frame ordered '
        'write replay, not original sub-frame write timing.')
    if system=='snes':
        for path in (bus,received,out/'capture.json'):report['sources'][str(path)]=sha(path)
    (out/'sweep-observer.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(system=system,observer_neutral=True,trace=str(trace))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--system',choices=('nes','snes'),required=True)
    for name in ('normal','core','out'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--rom',type=Path)
    capture(**vars(p.parse_args()))
