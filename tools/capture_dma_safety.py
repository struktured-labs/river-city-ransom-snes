"""Fresh same-ROM control or full-route DMA envelopes, with exact neutral execution checks."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha, verify_capture


def capture(build,candidate,reference,out,observed=False):
    if out.exists() or any(k.startswith('RCR_') for k in os.environ):
        raise ValueError('Fresh output and clean instrumentation environment required')
    proof=bound_report(build/'dma-safety-build.json');core=Path(proof['core'])
    if sha(core)!=proof['core_sha256']:raise ValueError('Changed observer binary')
    for p,h in proof['artifacts'].items():
        if sha(build/p)!=h:raise ValueError('Changed build artifact')
    baseline,old=verify_capture(reference)
    if observed and baseline['core_sha256']!=sha(core):raise ValueError('Need same-core unobserved control')
    trace=out.with_name(out.name+'-dma.csv')
    if trace.exists():raise ValueError('Existing DMA trace')
    sources={**proof['sources'],str(build/'dma-safety-build.json'):sha(build/'dma-safety-build.json')}
    for p in (Path(__file__),Path('tools/benchmark_capture.py'),Path('tools/smoke_libretro.py'),
              core,candidate/'manifest.json',candidate/'native-cpu.sfc',
              reference/'capture.json',reference/'timeline.json',reference/'audio.wav'):
        sources[str(p)]=sha(p)
    env=os.environ.copy()
    if observed:env['RCR_DMA_SAFETY_TRACE']=str(trace.resolve())
    subprocess.run([sys.executable,'-m','tools.benchmark_capture','--system','snes','--core',str(core),
        '--rom',str(candidate/'native-cpu.sfc'),'--title','build/reference-title-05','--walk','build/reference-walk-02',
        '--scenario','traversal-park-single-sweep','--frame-images','--full-ram-telemetry','--out',str(out)],
        env=env,check=True)
    receipt,rows=verify_capture(out)
    for key in ('rom_sha256','scenario_sha256','frames','audio_sha256'):
        if receipt[key]!=baseline[key]:raise ValueError('Execution changed: '+key)
    if not receipt['capture_complete'] or not baseline['capture_complete'] or rows!=old:
        raise ValueError('Incomplete or non-neutral full timeline')
    if any(r['fault'] or r['input_requested']!=r['input_delivered'] for r in rows):
        raise ValueError('Faulty input/execution')
    if observed:
        if not trace.stat().st_size:raise ValueError('Empty DMA trace')
        sources[str(trace)]=sha(trace)
    for p in (out/'capture.json',out/'timeline.json',out/'audio.wav'):
        sources[str(p)]=sha(p)
    for path,h in sources.items():
        if sha(Path(path))!=h:raise ValueError('Source changed: '+path)
    report=dict(observed=observed,observer_neutral=observed,reference=str(reference),
        frames=len(rows),sources=sources,trace=str(trace) if observed else None,
        scope='Fresh process; no restored clock. Exact full RAM/input/video/PCM equality. '
        'Unobserved run also checks source-built core against the prior qualified core. '
        'Only CPU general DMA envelopes; HDMA is outside this observer.')
    (out/'dma-capture.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(observed=observed,frames=len(rows),execution_identical=True)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('build','candidate','reference','out'):p.add_argument('--'+k,type=Path,required=True)
    p.add_argument('--observed',action='store_true')
    capture(**vars(p.parse_args()))
