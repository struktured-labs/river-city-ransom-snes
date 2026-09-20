"""Time qualified poll calls including JSR, helper jump and RTS overhead."""
import argparse
from collections import Counter
import csv
import json
import os
from pathlib import Path
import subprocess

from tools.benchmark_report import sha


def audit(oracle,core,out):
    qualified=json.loads((oracle/'report.json').read_text())
    if not qualified['passed'] or qualified['pad_pairs']!=65536:raise ValueError('Unqualified poll oracle')
    for p,h in qualified['sources'].items():
        if sha(Path(p))!=h:raise ValueError('Changed poll oracle source')
    out.mkdir(parents=True,exist_ok=False);results=[]
    for chunk in (0,1,7,31):
        arms=[]
        for optimized in (0,1):
            folder=oracle/f'chunk-{chunk:02d}-{optimized}'
            for p,h in qualified['cases'][chunk]['arms'][optimized].items():
                if sha(Path(p))!=h:raise ValueError('Changed qualified poll fixture')
            program=(folder/'test.bin').read_bytes()[:0x7d8e]
            if program.count(b'\x20\x8e\xfd')!=1:raise ValueError('Ambiguous poll call instruction')
            call=0x8000+program.index(b'\x20\x8e\xfd');bank=0xc1+chunk%8
            base=out/f'{chunk}-{optimized}';trace=base.with_suffix('.csv');ram=base.with_suffix('.ram')
            env={k:v for k,v in os.environ.items() if not k.startswith('RCR_')}
            env.update(RCR_SPAN_TRACE=str(trace),RCR_PROFILE_FIRST='0',RCR_PROFILE_LAST='1600',
                RCR_SPAN_PC0=f'{bank:02x}{call:04x}',RCR_SPAN_PC1=f'{bank:02x}{call+3:04x}')
            subprocess.run(['python3','tools/smoke_libretro.py','--core',str(core),'--rom',str(folder/'test.sfc'),
                '--kind','adapter','--frames','1600','--ram',str(ram),'--receipt',str(base.with_suffix('.json'))],
                env=env,check=True,capture_output=True,timeout=60)
            if sha(ram)!=sha(folder/'memory.ram'):raise ValueError('Timing observer changed complete WRAM')
            with trace.open() as stream:events=list(csv.reader(stream))
            if len(events)!=4096 or any(len(r)!=16 or int(r[0])!=i%2 or
                    r[5]!=f'{bank:02x}{call+(3 if i%2 else 0):04x}' for i,r in enumerate(events)):
                raise ValueError('Incomplete/wrong poll timing points')
            costs=[int(b[4])-int(a[4]) for a,b in zip(events[::2],events[1::2])]
            if any(c<=0 for c in costs):raise ValueError('Invalid poll elapsed clocks')
            arms.append(dict(costs=costs,histogram=dict(Counter(costs)),mean=sum(costs)/len(costs)))
        saved=[a-b for a,b in zip(arms[0]['costs'],arms[1]['costs'])]
        results.append(dict(chunk=chunk,arms=arms,saved_min=min(saved),saved_mean=sum(saved)/len(saved),saved_max=max(saved)))
    paths=[Path(__file__),Path('tools/benchmark_report.py'),Path('tools/smoke_libretro.py'),
        Path('tools/snes9x_span_trace.inc'),oracle/'report.json',core]
    report=dict(passed=all(r['saved_min']>0 for r in results),observer_neutral=True,results=results,
        sources={str(p):sha(p) for p in paths},files={str(p):sha(p) for p in out.iterdir() if p.is_file()},
        scope='Actual fixture JSR through returned continuation; includes jumps, stack traffic and events. '
              '8192 matched cached-pad cases. No enabled NMI interleaving, full game or physical SNAC qualification.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps([dict(chunk=r['chunk'],original_mean=r['arms'][0]['mean'],optimized_mean=r['arms'][1]['mean'],
        saved_min=r['saved_min'],saved_mean=r['saved_mean']) for r in results],indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('oracle','core','out'):p.add_argument('--'+name,type=Path,required=True)
    audit(**vars(p.parse_args()))
