"""Neutral full-route observation of the original NES sound driver's busy branch."""
import argparse
import json
import os
from pathlib import Path
import time
from tools.benchmark_report import sha,verify_capture
from tools.capture_combat_instructions import equivalent
from tools.capture_dsp_latency import capture as capture_dsp

POINTS=(0x8146,0x814b,0x819a,0x8020)
GUARDS={0x8146:'2cfe07304fa207',0x819a:'60',0x8020:'8a489848adfe0709808dfe07'}

def capture(candidate,core,normal,out):
    trace=out.with_name(out.name+'-sound-busy.csv')
    if out.exists() or trace.exists() or any(k.startswith('RCR_') for k in os.environ):raise ValueError('Fresh outputs and clean environment required')
    baseline,previous=verify_capture(normal);rom=candidate/'native-cpu.sfc';nes=Path('roms/river-city-ransom-us.nes')
    if baseline['rom_sha256']!=sha(rom) or baseline['core_sha256']!=sha(core):raise ValueError('Wrong control')
    if sha(nes)!='b95f8def04c0012604b7cc68cf4ed8f49b2dfe4beda6182051de4b2423bea7b1':raise ValueError('Wrong NES source')
    image=rom.read_bytes();original=nes.read_bytes()
    for at,pattern in GUARDS.items():
        expected=bytes.fromhex(pattern)
        if image[0x60000+at:0x60000+at+len(expected)]!=expected or original[16+0x14000+at-0x8000:16+0x14000+at-0x8000+len(expected)]!=expected:raise ValueError('Changed original sound branch')
    paths=(Path(__file__),Path('tools/capture_combat_instructions.py'),Path('tools/capture_dsp_latency.py'),Path('tools/snes9x_main_store.inc'),core.parent.parent/'cpuexec.cpp',core,rom,nes,normal/'capture.json')
    sources={str(p):sha(p) for p in paths}
    env=dict(RCR_MAIN_STORE_TRACE=str(trace.resolve()),**{f'RCR_MAIN_STORE_PC{i}':f'{pc:04x}' for i,pc in enumerate(POINTS)})
    start=time.monotonic()
    try:
        os.environ.update(env);capture_dsp(core,rom,out)
    finally:
        for k in env:os.environ.pop(k,None)
    replay=time.monotonic()-start
    receipt,rows=verify_capture(out);equivalent(receipt,rows,baseline,previous)
    if not trace.stat().st_size or any(sha(Path(p))!=h for p,h in sources.items()):raise ValueError('Missing trace or changed source')
    sources.update({str(p):sha(p) for p in (trace,out/'capture.json')})
    report=dict(sources=sources,trace=str(trace),observer_neutral=True,points=POINTS,guards=GUARDS,frames=len(rows),replay_seconds=replay,total_seconds=time.monotonic()-start,scope=__doc__)
    (out/'sound-busy.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('frames','observer_neutral','replay_seconds','total_seconds')}))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('candidate','core','normal','out'):p.add_argument('--'+k,type=Path,required=True)
    capture(**vars(p.parse_args()))
