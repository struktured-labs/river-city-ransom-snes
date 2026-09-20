"""Full-route OAM plus explicit black spans, with separate compatibility and neutrality checks."""
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


def capture(build,candidate,reference,out,observed=False):
    proof=bound_report(build/'sprite-event-build.json');core=Path(proof['core'])
    trace=out.with_suffix('.csv')
    if out.exists() or trace.exists() or any(k.startswith('RCR_') for k in os.environ):
        raise ValueError('Fresh output and clean observer environment required')
    if sha(core)!=proof['core_sha256'] or any(sha(build/p)!=h for p,h in proof['artifacts'].items()):
        raise ValueError('Changed observer build')
    if "rcr_sprite_event('B', 255);" not in (build/'gfx.cpp').read_text():raise ValueError('Missing black span hook')
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
        env.update(RCR_SPRITE_EVENT_TRACE=str(trace.resolve()),RCR_SPRITE_FIRST='0',RCR_SPRITE_LAST=str(baseline['frames']))
    start=time.monotonic()
    subprocess.run([sys.executable,'-m','tools.benchmark_capture','--system','snes','--core',str(core),
        '--rom',str(candidate/'native-cpu.sfc'),'--title','build/reference-title-05','--walk','build/reference-walk-02',
        '--scenario','traversal-park-single-sweep','--frame-images','--full-ram-telemetry','--out',str(out)],env=env,check=True)
    replay_seconds=time.monotonic()-start
    receipt,rows=verify_capture(out)
    if receipt['core_sha256']!=sha(core):raise ValueError('Wrong capture core')
    if observed:equivalent(receipt,rows,baseline,before)
    elif (not receipt['capture_complete'] or not baseline['capture_complete'] or rows!=before or
          any(receipt[k]!=baseline[k] for k in ('rom_sha256','scenario_sha256','frames','audio_sha256'))):
        raise ValueError('Cross-core compatibility failed')
    if any(r['fault'] or r['input_requested']!=r['input_delivered'] for r in rows):raise ValueError('Faulty execution')
    if observed:
        if not trace.stat().st_size:raise ValueError('Missing trace')
        sources[str(trace)]=sha(trace)
    for p in (out/'capture.json',out/'timeline.json',out/'audio.wav'):sources[str(p)]=sha(p)
    if any(sha(Path(p))!=h for p,h in sources.items()):raise ValueError('Changed source')
    report=dict(sources=sources,frames=len(rows),observed=observed,observer_neutral=observed,
        reference=str(reference),trace=str(trace) if observed else None,replay_seconds=replay_seconds,
        total_seconds=time.monotonic()-start,scope=__doc__+' Original complete timeline/native PCM preserved. '
        'B records actual forced-black spans; it is not substituted render coverage. All D/E/R/B events retained, CPU source hooks disabled.')
    (out/'oam-blank-route.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(frames=len(rows),observed=observed,replay_seconds=replay_seconds,total_seconds=report['total_seconds'])))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('build','candidate','reference','out'):p.add_argument('--'+k,type=Path,required=True)
    p.add_argument('--observed',action='store_true')
    capture(**vars(p.parse_args()))
