"""Observe integrated staged game without legacy direct-receiver packet assumptions."""
import argparse
import csv
import json
import os
from pathlib import Path
import time
import numpy as np
from tools import benchmark_capture as bench
from tools.benchmark_report import sha,verify_capture
from tools.capture_combat_instructions import equivalent
from tools.audit_main_store_latency import parse
from tools.audit_ordinary_route_timing import cadence


def capture(candidate,core,normal,out):
    if out.exists() or any(k.startswith('RCR_') for k in os.environ):raise ValueError('Fresh capture required')
    baseline,plain=verify_capture(normal);rom=candidate/'native-cpu.sfc'
    if sha(rom)!=baseline['rom_sha256'] or sha(core)!=baseline['core_sha256']:raise ValueError('Different control')
    paths=[Path(__file__),Path('tools/benchmark_capture.py'),Path('tools/benchmark_report.py'),
        Path('tools/capture_combat_instructions.py'),Path('tools/audit_main_store_latency.py'),
        Path('tools/audit_ordinary_route_timing.py'),Path('tools/snes9x_main_store.inc'),Path('tools/snes9x_dsp_latency.inc'),core,rom,
        core.parent.parent/'apu/bapu/smp/core.cpp',core.parent.parent/'cpuexec.cpp',normal/'capture.json']
    sources={str(p):sha(p) for p in paths}
    labels={r.split()[2].lstrip('.'):int(r.split()[1],16) for r in (candidate/'native_runtime.lbl').read_text().splitlines()}
    points={0:labels['gameplay_iteration_start'],1:0xf282,2:labels['camera_deferred_nmi_exit']+2,3:0xf2da}
    traces={k:out.with_name(out.name+s) for k,s in (('RCR_DSP_LATENCY_TRACE','-dsp.csv'),('RCR_DSP_DAC_PCM','-dac.pcm'),('RCR_MAIN_STORE_TRACE','-main.csv'))}
    if any(p.exists() for p in traces.values()):raise ValueError('Existing trace')
    env={k:str(p.resolve()) for k,p in traces.items()};env.update({f'RCR_MAIN_STORE_PC{k}':f'{v:04x}' for k,v in points.items()})
    refs=dict(menu=(Path('build/reference-title-05'),600),settings=(Path('build/reference-walk-02'),600),
        story=(Path('build/reference-walk-02'),900),street=(Path('build/reference-walk-02'),1800))
    start=time.monotonic()
    try:
        os.environ.update(env);bench.capture(core,rom,'snes',refs,out,'traversal-park-single-sweep',True,True)
    finally:
        for k in env:os.environ.pop(k,None)
    replay=time.monotonic()-start
    receipt,rows=verify_capture(out);equivalent(receipt,rows,baseline,plain)
    loops,censored=parse(csv.reader(traces['RCR_MAIN_STORE_TRACE'].open()),points,len(rows),rom.read_bytes())
    for loop in loops:loop['nmi_advances']=(loop['finish']['nmi']-loop['start']['nmi'])&65535
    cad=cadence(loops,rows)
    ready=[int(r[2]) for r in csv.reader(traces['RCR_DSP_LATENCY_TRACE'].open()) if r[0]=='R']
    pcm=np.fromfile(traces['RCR_DSP_DAC_PCM'],dtype='<i2').astype(np.int32).reshape(-1,2)
    summary=dict(capture_complete=receipt['capture_complete'],frames=len(rows),observer_neutral=True,
        ready_events=len(ready),samples=len(pcm),peak=int(np.abs(pcm).max()),clipped=int((np.abs(pcm)>=32767).sum()),
        max_adjacent_step=int(np.abs(np.diff(pcm,axis=0)).max()),
        rooms={k:{n:v[n] for n in ('intervals','frame_histogram','busy_intervals','passed')} for k,v in cad['rooms'].items()})
    if any(sha(Path(p))!=h for p,h in sources.items()):raise ValueError('Changed source')
    sources.update({str(p):sha(p) for p in traces.values()})
    report=dict(summary=summary,ready_ticks=ready,cadence=cad,censored=censored,sources=sources,
        replay_seconds=replay,total_seconds=time.monotonic()-start,release_ready=False,scope=__doc__+
        ' All ready events retained including startup. Old packet IDs are invalid for staged copy and not used. '
        'An incomplete route remains failed, not a full-route pass.')
    (out/'timed-game-audio.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(summary))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('candidate','core','normal','out'):p.add_argument('--'+k,type=Path,required=True)
    capture(**vars(p.parse_args()))
