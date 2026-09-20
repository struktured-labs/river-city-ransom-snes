"""Full boot-driven OAM DMA/render observation; no CPU hooks or emulated accesses."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha,verify_capture
from tools.capture_combat_instructions import equivalent


def capture(candidate,reference,out,observed=False,finalize_existing=False):
    build=Path('.deps/snes9x-sprite-events-3243')
    proof=bound_report(build/'sprite-event-build.json');core=Path(proof['core'])
    trace=out.with_suffix('.csv')
    if (out.exists() and not finalize_existing) or trace.exists() or any(k.startswith('RCR_') for k in os.environ):
        raise ValueError('Fresh output and clean observer environment required')
    if finalize_existing and (observed or (out/'oam-route.json').exists()):
        raise ValueError('Only unpublished unobserved controls may be finalized')
    if sha(core)!=proof['core_sha256'] or any(sha(build/p)!=h for p,h in proof['artifacts'].items()):
        raise ValueError('Changed observer build')
    baseline,before=verify_capture(reference)
    if baseline['rom_sha256']!=sha(candidate/'native-cpu.sfc') or baseline['scenario_name']!='traversal-park-single-sweep':
        raise ValueError('Wrong full-route control')
    if observed and baseline['core_sha256']!=sha(core):raise ValueError('Same-core control required')
    sources=dict(proof['sources'])
    for p in (Path(__file__),Path('tools/benchmark_capture.py'),Path('tools/benchmark_report.py'),
              Path('tools/capture_combat_instructions.py'),Path('tools/smoke_libretro.py'),
              build/'sprite-event-build.json',core,candidate/'native-cpu.sfc',candidate/'manifest.json',
              reference/'capture.json',reference/'timeline.json',reference/'audio.wav'):
        sources[str(p)]=sha(p)
    env=os.environ.copy()
    if observed:
        env.update(RCR_SPRITE_EVENT_TRACE=str(trace.resolve()),RCR_SPRITE_FIRST='0',
                   RCR_SPRITE_LAST=str(baseline['frames']))
    started=time.monotonic()
    if not finalize_existing:
        subprocess.run([sys.executable,'-m','tools.benchmark_capture','--system','snes','--core',str(core),
            '--rom',str(candidate/'native-cpu.sfc'),'--title','build/reference-title-05','--walk','build/reference-walk-02',
            '--scenario','traversal-park-single-sweep','--frame-images','--full-ram-telemetry','--out',str(out)],env=env,check=True)
    replay_seconds=None if finalize_existing else time.monotonic()-started
    receipt,rows=verify_capture(out)
    if receipt['core_sha256']!=sha(core):raise ValueError('Wrong capture core')
    if observed:
        equivalent(receipt,rows,baseline,before)
    elif (not receipt['capture_complete'] or not baseline['capture_complete'] or rows!=before
          or any(receipt[k]!=baseline[k] for k in ('rom_sha256','scenario_sha256','frames','audio_sha256'))):
        raise ValueError('Cross-core compatibility failed')
    if any(r['fault'] or r['input_requested']!=r['input_delivered'] for r in rows):raise ValueError('Faulty execution')
    if observed:
        if not trace.stat().st_size:raise ValueError('Missing OAM trace')
        sources[str(trace)]=sha(trace)
    for p in (out/'capture.json',out/'timeline.json',out/'audio.wav'):sources[str(p)]=sha(p)
    if any(sha(Path(p))!=h for p,h in sources.items()):raise ValueError('Changed source')
    report=dict(sources=sources,frames=len(rows),observed=observed,observer_neutral=observed,
        core_sha256=sha(core),reference=str(reference),trace=str(trace) if observed else None,
        elapsed_seconds=time.monotonic()-started,replay_seconds=replay_seconds,
        finalized_existing_control=finalize_existing,scope=__doc__+
        ' Complete primary timeline/native PCM equality. Unobserved comparison across cores is separately a compatibility check. '
        'D/E retain every general OAM DMA, R retains complete actual OAM before rendering; source/preparation CPU hooks are disabled.')
    (out/'oam-route.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(frames=len(rows),observed=observed,seconds=report['elapsed_seconds'])))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('candidate','reference','out'):p.add_argument('--'+k,type=Path,required=True)
    p.add_argument('--observed',action='store_true')
    p.add_argument('--finalize-existing',action='store_true')
    capture(**vars(p.parse_args()))
