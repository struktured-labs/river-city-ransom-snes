"""Capture real IRQ CPU context with full same-core timeline/PCM neutrality."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha, verify_capture


def capture(build,candidate,reference,out,observed=False):
    if out.exists() or any(k.startswith('RCR_') for k in os.environ):raise ValueError('Fresh output/clean environment required')
    started=time.monotonic();proof=bound_report(build/'irq-context-build.json');core=Path(proof['core'])
    if sha(core)!=proof['core_sha256']:raise ValueError('Changed core')
    for p,h in proof['artifacts'].items():
        if sha(build/p)!=h:raise ValueError('Changed core build artifact')
    baseline,previous=verify_capture(reference);rom=candidate/'native-cpu.sfc'
    if baseline['rom_sha256']!=sha(rom) or not baseline['capture_complete']:raise ValueError('Wrong/incomplete cartridge control')
    if observed and baseline['core_sha256']!=sha(core):raise ValueError('Need exact same-core control')
    trace=out.with_name(out.name+'-irq.csv')
    if trace.exists():raise ValueError('Trace exists')
    sources=dict(proof['sources']);sources[str(build/'irq-context-build.json')]=sha(build/'irq-context-build.json')
    for p in (Path(__file__),Path('tools/benchmark_capture.py'),Path('tools/benchmark_report.py'),
              Path('tools/smoke_libretro.py'),rom,candidate/'manifest.json',reference/'capture.json',
              reference/'timeline.json',reference/'audio.wav',core):sources[str(p)]=sha(p)
    env=dict(os.environ)
    if observed:env['RCR_IRQ_CONTEXT_TRACE']=str(trace.resolve())
    subprocess.run([sys.executable,'-m','tools.benchmark_capture','--system','snes','--core',str(core),
        '--rom',str(rom),'--title','build/reference-title-05','--walk','build/reference-walk-02',
        '--scenario',baseline['scenario_name'],'--frame-images','--full-ram-telemetry','--out',str(out)],env=env,check=True)
    receipt,rows=verify_capture(out)
    if not receipt['capture_complete'] or rows!=previous or any(receipt[k]!=baseline[k] for k in
            ('rom_sha256','audio_sha256','frames','scenario_sha256')):raise ValueError('Changed execution or incomplete capture')
    if any(r['fault'] or r['input_requested']!=r['input_delivered'] for r in rows):raise ValueError('Game/input fault')
    if observed:
        if not trace.stat().st_size:raise ValueError('No actual IRQs')
        sources[str(trace)]=sha(trace)
    for p in (out/'capture.json',out/'timeline.json',out/'audio.wav'):sources[str(p)]=sha(p)
    if any(sha(Path(p))!=h for p,h in sources.items()):raise ValueError('Changed source during capture')
    report=dict(sources=sources,observed=observed,observer_neutral=observed,reference=str(reference),
        trace=str(trace) if observed else None,frames=len(rows),seconds=time.monotonic()-started,
        scope=__doc__+' Unobserved control also checks cross-core compatibility, which is not observer neutrality.')
    (out/'irq-context-capture.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('observed','observer_neutral','frames','seconds')}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('build','candidate','reference','out'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--observed',action='store_true');capture(**vars(p.parse_args()))
