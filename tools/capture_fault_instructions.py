"""Neutral instruction diagnosis of a faulted route; faults remain failures, not waived."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from tools.benchmark_report import sha, verify_capture


def capture(candidate,core,normal,out,first,last):
    trace=out.with_suffix('.csv')
    if out.exists() or trace.exists() or any(k.startswith('RCR_') for k in os.environ):
        raise ValueError('Fresh outputs and clean environment required')
    started=time.monotonic();baseline,old=verify_capture(normal)
    rom=candidate/'native-cpu.sfc'
    if baseline['rom_sha256']!=sha(rom) or baseline['core_sha256']!=sha(core):
        raise ValueError('Wrong exact-ROM/core control')
    if not 1<=first<=last<=len(old) or not any(r['fault'] for r in old):
        raise ValueError('Need bounded window and retained faulted control')
    paths=[Path(__file__),Path('tools/benchmark_capture.py'),Path('tools/benchmark_report.py'),
           Path('tools/snes9x_instruction_trace.inc'),core.parent.parent/'cpuexec.cpp',
           core,rom,candidate/'manifest.json',normal/'capture.json',normal/'timeline.json',normal/'audio.wav']
    sources={str(p):sha(p) for p in paths}
    verified=time.monotonic()
    env=os.environ.copy();env.update(RCR_INSTRUCTION_TRACE=str(trace.resolve()),
        RCR_PROFILE_FIRST=str(first),RCR_PROFILE_LAST=str(last))
    subprocess.run([sys.executable,'-m','tools.benchmark_capture','--system','snes',
        '--core',str(core),'--rom',str(rom),'--title','build/reference-title-05',
        '--walk','build/reference-walk-02','--scenario','traversal-park-single-sweep',
        '--frame-images','--full-ram-telemetry','--out',str(out)],env=env,check=True)
    captured=time.monotonic();receipt,rows=verify_capture(out)
    if any(receipt[k]!=baseline[k] for k in ('core_sha256','rom_sha256','scenario_sha256','frames','audio_sha256')) or rows!=old:
        raise ValueError('Observer changed complete faulted execution')
    if not receipt['capture_complete'] or any(r['input_requested']!=r['input_delivered'] for r in rows):
        raise ValueError('Incomplete route or input mismatch')
    if not trace.stat().st_size or receipt['instruction_trace']['sha256']!=sha(trace):
        raise ValueError('Missing or changed instruction trace')
    if any(sha(p)!=h for p,h in sources.items()):raise ValueError('Changed source')
    for p in (trace,out/'capture.json',out/'timeline.json',out/'audio.wav'):sources[str(p)]=sha(p)
    faults=[dict(frame=r['frame'],phase=r['phase'],fault=r['fault'],registers=r['fault_registers'])
            for r in rows if r['fault']]
    report=dict(sources=sources,observer_neutral=True,release_ready=False,game_passed=False,
                frames=len(rows),first=first,last=last,trace=str(trace),faults=faults,
                timing=dict(verify_control_seconds=verified-started,replay_seconds=captured-verified,
                            verify_result_seconds=time.monotonic()-captured),scope=__doc__)
    (out/'fault-instructions.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(observer_neutral=True,game_passed=False,fault_frames=len(faults),timing=report['timing'])))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for k in ('candidate','core','normal','out'):parser.add_argument('--'+k,type=Path,required=True)
    for k in ('first','last'):parser.add_argument('--'+k,type=int,required=True)
    capture(**vars(parser.parse_args()))
