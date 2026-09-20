"""Same-core control and intentional zero-volume suppression with unchanged CPU execution."""
import argparse
import csv
import json
import os
from pathlib import Path
import subprocess
import sys

from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha,verify_capture
from tools.capture_nes_audio_events import POINTS


def validate_log(records,drops):
    expected=[['D',str(w['frame']),str(w['clock']),f'{w["pc"]:04x}',
               f'{w["register"]+0x4000:04x}',str(w['value'])] for w in drops]
    expected.append(['E',str(len(drops))])
    if records!=expected:raise ValueError('Executed suppression differs from exact complete schedule')
    return len(drops)


def nonaudio(rows):
    return [dict(r,audio=dict(samples=r['audio']['samples'])) for r in rows]


def capture(core,plan,out,suppress=False,normal=None):
    if out.exists() or any(k.startswith('RCR_') for k in os.environ):
        raise ValueError('Fresh output and clean observer environment required')
    if suppress!=(normal is not None):raise ValueError('Mutation requires its explicit same-core control')
    planned=bound_report(plan/'report.json')
    build=bound_report(core.parent/'volume-suppression-build.json')
    if build['core_sha256']!=sha(core):raise ValueError('Changed mutation/control core')
    reference=Path(planned['original_capture']);prior=bound_report(reference/'driver-writes.json')
    original,original_rows=verify_capture(reference)
    rom=Path('roms/river-city-ransom-us.nes')
    if sha(rom)!=planned['rom_sha256']:raise ValueError('Different original ROM')
    paths={name:out.with_name(out.name+suffix) for name,suffix in (
        ('events','-events.csv'),('writes','-writes.csv'),('suppressed','-suppressed.csv'))}
    if any(p.exists() for p in paths.values()):raise ValueError('Trace already exists')
    env=dict(os.environ,RCR_NES_APU_WRITE_CLOCK=str(paths['writes'].resolve()),
        RCR_NES_EVENT_TRACE=str(paths['events'].resolve()),RCR_NES_TRACE_FIRST='1',
        RCR_NES_TRACE_LAST=str(planned['source_frames']))
    env.update({f'RCR_NES_EVENT_PC{k}':v for k,v in POINTS.items()})
    if suppress:
        env.update(RCR_NES_VOLUME_SUPPRESS=str((plan/'schedule.csv').resolve()),
                   RCR_NES_VOLUME_SUPPRESS_LOG=str(paths['suppressed'].resolve()))
    sources={**planned['sources'],**build['sources'],**prior['sources']}
    for p in (Path(__file__),Path('tools/benchmark_capture.py'),Path('tools/smoke_libretro.py'),
        Path('tools/fceumm_volume_suppression.inc'),Path('tools/fceumm_apu_write_clock.inc'),
        plan/'report.json',plan/'schedule.csv',core,core.parent/'volume-suppression-build.json',
        reference/'driver-writes.json',reference/'capture.json',reference/'timeline.json',reference/'audio.wav'):
        sources[str(p)]=sha(p)
    subprocess.run([sys.executable,'-m','tools.benchmark_capture','--system','nes','--core',str(core),
        '--rom',str(rom),'--title','build/reference-title-05','--walk','build/reference-walk-02',
        '--scenario','traversal-park-single-sweep','--frame-images','--full-ram-telemetry','--out',str(out)],
        env=env,check=True)
    receipt,rows=verify_capture(out)
    if (not receipt['capture_complete'] or not nonaudio(rows)==nonaudio(original_rows) or
        any(receipt[k]!=original[k] for k in ('system','rom_sha256','scenario_sha256','frames'))):
        raise ValueError('Mutation/control changed game state, input, video or sample timing')
    for name in ('events','writes'):
        if sha(paths[name])!=sha(Path(prior[name])):
            raise ValueError('Original CPU writes or exact-PC clocks changed: '+name)
    actual=0
    if suppress:
        nb=bound_report(normal/'volume-sensitivity.json');nr,nrows=verify_capture(normal)
        if nb['suppressed'] or nr['core_sha256']!=receipt['core_sha256'] or nonaudio(nrows)!=nonaudio(rows):
            raise ValueError('Different/modified same-core control')
        sources.update(nb['sources']);sources[str(normal/'volume-sensitivity.json')]=sha(normal/'volume-sensitivity.json')
        with paths['suppressed'].open() as f:actual=validate_log(list(csv.reader(f)),planned['drops'])
        sources[str(paths['suppressed'])]=sha(paths['suppressed'])
    elif rows!=original_rows or receipt['audio_sha256']!=original['audio_sha256']:
        raise ValueError('Unmodified new-core control differs from original NES')
    for p in (paths['events'],paths['writes'],out/'capture.json',out/'timeline.json',out/'audio.wav'):
        sources[str(p)]=sha(p)
    for p,h in sources.items():
        if sha(Path(p))!=h:raise ValueError('Source changed: '+p)
    result=dict(suppressed=suppress,executed_suppressed_writes=actual,
        cpu_write_intent_identical=True,exact_pc_clocks_identical=True,
        nonaudio_and_sample_timing_identical=True,normal=None if normal is None else str(normal),
        traces={k:str(v) for k,v in paths.items() if v.exists()},sources=sources,
        release_ready=False,scope=__doc__+' Mutation audio is NOT an unmodified NES reference. '
        'Only listed APU dispatches are omitted; final writes/reloads and all CPU clocks remain. '
        'All exclusions and unknown/mode-changing runs remain unchanged.')
    (out/'volume-sensitivity.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('sources','traces')}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('core','plan','out'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--normal',type=Path);p.add_argument('--suppress',action='store_true')
    capture(**vars(p.parse_args()))
