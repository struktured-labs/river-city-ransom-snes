"""Fresh-process combat loop trace with exact sites and immutable source receipt."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from tools.benchmark_report import sha, verify_capture


def capture(system, core, normal, candidate, out):
    baseline,_=verify_capture(normal)
    if baseline['system']!=system or baseline['scenario_name']!='combat-knockdown-audio':
        raise ValueError('Need matching combat baseline')
    rom=candidate/'native-cpu.sfc' if system=='snes' else Path('roms/river-city-ransom-us.nes')
    if sha(rom)!=baseline['rom_sha256']:raise ValueError('Different ROM')
    trace=out.with_name(out.name+'.csv')
    if out.exists() or trace.exists():raise ValueError('Need new outputs')
    env=os.environ.copy()
    if any(k.startswith(('RCR_MAIN_','RCR_NES_','RCR_RENDER_')) for k in env):
        raise ValueError('Unexpected inherited trace settings')
    paths=[Path(__file__),Path('tools/benchmark_capture.py'),Path('tools/smoke_libretro.py'),
           rom,core,normal/'capture.json']
    if system=='snes':
        labels=candidate/'native_runtime.lbl'
        symbols={s.split()[2].lstrip('.'):int(s.split()[1],16) for s in labels.read_text().splitlines()}
        points={0:symbols['gameplay_iteration_start'],1:0xf282,
                2:symbols['camera_deferred_nmi_exit']+2,3:0xf2da}
        env['RCR_MAIN_STORE_TRACE']=str(trace.resolve())
        for i,pc in points.items():env[f'RCR_MAIN_STORE_PC{i}']=f'{pc:04x}'
        paths += [labels,Path('tools/snes9x_main_store.inc'),Path('.deps/snes9x/cpuexec.cpp')]
    else:
        points={0:0xf27d,1:0xf282,2:0xf2da}
        env.update(RCR_NES_EVENT_TRACE=str(trace.resolve()),RCR_NES_TRACE_FIRST='1',
                   RCR_NES_TRACE_LAST=str(baseline['frames']))
        for i,pc in points.items():env[f'RCR_NES_EVENT_PC{i}']=f'{pc:04x}'
        paths += [Path('tools/fceumm_queue_trace.inc'),Path('.deps/fceumm-raster/src/x6502.c')]
    sources={str(p):sha(p) for p in paths}
    subprocess.run([sys.executable,'-m','tools.benchmark_capture','--system',system,'--core',str(core),
        '--rom',str(rom),'--title','build/reference-title-05','--walk','build/reference-walk-02',
        '--scenario','combat-knockdown-audio','--frame-images','--full-ram-telemetry','--out',str(out)],
        env=env,check=True)
    for p,digest in sources.items():
        if sha(Path(p))!=digest:raise ValueError('Changed source: '+p)
    if not trace.stat().st_size:raise ValueError('Empty trace')
    report=dict(system=system,points={str(k):f'{v:04x}' for k,v in points.items()},
        trace=str(trace),sources={**sources,str(trace):sha(trace),str(out/'capture.json'):sha(out/'capture.json')},
        scope='Exact original main/input/finish sites; SNES also observes camera commit. '
              'Read-only host observations; no original game RAM or input changes. Neutrality checked separately.')
    (out/'combat-observer.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--system',choices=('nes','snes'),required=True)
    for name in ('core','normal','candidate','out'):p.add_argument('--'+name,type=Path,required=True)
    capture(**vars(p.parse_args()))
