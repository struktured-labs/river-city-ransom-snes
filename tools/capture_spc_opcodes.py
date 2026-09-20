"""Full-route neutral capture with a narrow, read-only SPC opcode window."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from tools.benchmark_report import sha, verify_capture
from tools.capture_combat_instructions import equivalent

def capture(build, candidate, reference, out, first=None, last=None):
    observed = first is not None
    if observed != (last is not None) or observed and not 0 <= first < last:
        raise ValueError('Both ordered tick bounds required')
    trace=out.with_suffix('.csv')
    if out.exists() or trace.exists() or any(k.startswith('RCR_') for k in os.environ):
        raise ValueError('Fresh outputs and clean observer environment required')
    proof=json.loads((build/'spc-opcode-build.json').read_text())
    for p,h in proof['sources'].items():
        if sha(Path(p)) != h: raise ValueError('Changed core source: '+p)
    for p,h in proof['artifacts'].items():
        if sha(build/p) != h: raise ValueError('Changed core artifact: '+p)
    core=Path(proof['core']); rom=candidate/'native-cpu.sfc'
    baseline, previous=verify_capture(reference)
    if baseline['rom_sha256']!=sha(rom): raise ValueError('Wrong reference ROM')
    if observed and baseline['core_sha256']!=sha(core): raise ValueError('Neutrality requires exact same core')
    paths=(Path(__file__),build/'spc-opcode-build.json',core,rom,reference/'capture.json',
           Path('tools/benchmark_capture.py'),Path('tools/benchmark_report.py'),
           Path('tools/capture_combat_instructions.py'),Path('tools/smoke_libretro.py'))
    sources={str(p):sha(p) for p in paths}
    env=os.environ.copy()
    if observed: env.update(RCR_SPC_OP_TRACE=str(trace.resolve()),RCR_SPC_OP_FIRST=str(first),RCR_SPC_OP_LAST=str(last))
    start=time.monotonic()
    subprocess.run([sys.executable,'-m','tools.benchmark_capture','--system','snes',
        '--core',str(core),'--rom',str(rom),'--title','build/reference-title-05',
        '--walk','build/reference-walk-02','--scenario','traversal-park-single-sweep',
        '--frame-images','--full-ram-telemetry','--out',str(out)],env=env,check=True,stdout=subprocess.DEVNULL)
    replay=time.monotonic()-start
    receipt, rows=verify_capture(out)
    comparison=dict(baseline)
    if not observed: comparison['core_sha256']=receipt['core_sha256']
    equivalent(receipt,rows,comparison,previous)
    if observed and not trace.stat().st_size: raise ValueError('Missing opcode trace')
    if any(sha(Path(p))!=h for p,h in sources.items()): raise ValueError('Changed source during capture')
    sources[str(out/'capture.json')]=sha(out/'capture.json')
    if observed: sources[str(trace)]=sha(trace)
    report=dict(sources=sources,observer_neutral=observed,cross_core_compatible=not observed,
                first=first,last=last,trace=str(trace) if observed else None,
                frames=len(rows),replay_seconds=replay,total_seconds=time.monotonic()-start,scope=__doc__)
    (out/'spc-opcodes.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='sources'}))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('build','candidate','reference','out'): p.add_argument('--'+k,type=Path,required=True)
    for k in ('first','last'): p.add_argument('--'+k,type=int)
    capture(**vars(p.parse_args()))
