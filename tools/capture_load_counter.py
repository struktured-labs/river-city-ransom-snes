"""Observe the original game counter at main boundaries and its load-reset site.

Fresh process, existing host-only hooks, exact normal timeline/PCM required.
No emulator or ROM edits; no altered input policy or savestate injection.
"""
import argparse
from contextlib import nullcontext
import json
import os
from pathlib import Path

from tools import benchmark_capture as benchmark
from tools.benchmark_report import sha, verify_capture
from tools.capture_combat_instructions import equivalent
from tools.combat_campaign import installed


def capture(system,core,normal,candidate,out):
    if out.exists() or any(k.startswith('RCR_') for k in os.environ):raise ValueError('Fresh process/output required')
    control=json.loads((normal/'capture.json').read_text())
    policy='running-jumps' if system=='snes' else None
    context=installed(policy) if policy else nullcontext('traversal-park-single-sweep')
    trace=out.with_name(out.name+'-counter.csv')
    if trace.exists():raise ValueError('Trace exists')
    rom=candidate/'native-cpu.sfc' if system=='snes' else Path('roms/river-city-ransom-us.nes')
    points={0:0xf27d,1:0xf282,2:0xf2da,3:0xe05c,4:0xe05f}
    if system=='snes':
        symbols={r.split()[2].lstrip('.'):int(r.split()[1],16) for r in (candidate/'native_runtime.lbl').read_text().splitlines()}
        points[0]=symbols['gameplay_iteration_start']
    marker=b'RCR_PROFILE_EVENT_TRACE' if system=='snes' else b'RCR_NES_EVENT_TRACE'
    if (sha(core)!=control['core_sha256'] or sha(rom)!=control['rom_sha256'] or marker not in core.read_bytes()):
        raise ValueError('Need same core/ROM and existing host observer')
    paths=[Path(__file__),Path('tools/benchmark_capture.py'),Path('tools/benchmark_report.py'),
        Path('tools/capture_combat_instructions.py'),Path('tools/combat_campaign.py'),
        Path('tools/smoke_libretro.py'),normal/'capture.json',core,rom]
    paths += ([Path('tools/snes9x_cpu_profile.inc'),Path('.deps/snes9x/cpuexec.cpp'),candidate/'manifest.json',candidate/'native_runtime.lbl']
              if system=='snes' else [Path('tools/fceumm_queue_trace.inc'),Path('.deps/fceumm-raster/src/x6502.c')])
    sources={str(p):sha(p) for p in paths}
    prefix='RCR_PROFILE' if system=='snes' else 'RCR_NES'
    env={prefix+'_EVENT_TRACE':str(trace.resolve())}
    env.update({prefix+'_EVENT_PC'+str(k):f'{v:04x}' for k,v in points.items()})
    env.update({prefix+('_FIRST' if system=='snes' else '_TRACE_FIRST'):'1',
                prefix+('_LAST' if system=='snes' else '_TRACE_LAST'):str(control['frames'])})
    refs={'menu':(Path('build/reference-title-05'),600),'settings':(Path('build/reference-walk-02'),600),
          'story':(Path('build/reference-walk-02'),900),'street':(Path('build/reference-walk-02'),1800)}
    try:
        os.environ.update(env)
        with context as scenario:
            baseline,plain=verify_capture(normal)
            if baseline['scenario_name']!=scenario:raise ValueError('Different input scenario')
            benchmark.capture(core,rom,system,refs,out,scenario,True,True,ppu_telemetry=system=='nes')
            receipt,rows=verify_capture(out)
            equivalent(receipt,rows,baseline,plain)
    finally:
        for k in env:os.environ.pop(k,None)
    if any(sha(Path(p))!=v for p,v in sources.items()) or not trace.stat().st_size:
        raise ValueError('Changed source / missing events')
    for p in (out/'capture.json',out/'timeline.json',out/'audio.wav',trace):sources[str(p)]=sha(p)
    report=dict(system=system,observer_neutral=True,points={str(k):f'{v:04x}' for k,v in points.items()},
        trace=str(trace),sources=sources,scope=__doc__)
    (out/'counter-observer.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),frames=receipt['frames'],observer_neutral=True)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--system',choices=('nes','snes'),required=True)
    for name in ('core','normal','candidate','out'):p.add_argument('--'+name,type=Path,required=True)
    capture(**vars(p.parse_args()))
