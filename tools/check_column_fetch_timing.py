"""Time qualified column calls; include entry jumps and original return overhead."""
import argparse
import csv
import json
import os
from pathlib import Path
import subprocess

from tools.benchmark_report import sha


def audit(oracle,core,out):
    qualified=json.loads((oracle/'report.json').read_text())
    if not qualified['passed'] or qualified['cases']!=5120:raise ValueError('Unqualified column oracle')
    for p,h in qualified['sources'].items():
        if sha(Path(p))!=h:raise ValueError('Changed column source')
    out.mkdir(parents=True,exist_ok=False);results=[]
    for chunk in (0,7,28,32,47,63,79):
        arms=[]
        for optimized in (0,1):
            folder=oracle/f'chunk-{chunk:03d}-{optimized}'
            for p,h in qualified['chunks'][chunk]['arms'][optimized].items():
                if sha(Path(p))!=h:raise ValueError('Changed qualified column fixture')
            program=(folder/'test.bin').read_bytes()[:0x42c3]
            if program.count(b'\x20\xc3\xc2')!=1:raise ValueError('Ambiguous column call')
            call=0x8000+program.index(b'\x20\xc3\xc2');bank=0xc1+chunk%8
            base=out/f'{chunk}-{optimized}';trace=base.with_suffix('.csv');ram=base.with_suffix('.ram')
            env={k:v for k,v in os.environ.items() if not k.startswith('RCR_')}
            env.update(RCR_SPAN_TRACE=str(trace),RCR_PROFILE_FIRST='0',RCR_PROFILE_LAST='120',
                RCR_SPAN_PC0=f'{bank:02x}{call:04x}',RCR_SPAN_PC1=f'{bank:02x}{call+3:04x}')
            subprocess.run(['python3','tools/smoke_libretro.py','--core',str(core),'--rom',str(folder/'test.sfc'),
                '--kind','adapter','--frames','120','--ram',str(ram),'--receipt',str(base.with_suffix('.json'))],
                env=env,check=True,capture_output=True,timeout=30)
            if sha(ram)!=sha(folder/'memory.ram'):raise ValueError('Observer changed full WRAM')
            with trace.open() as stream:events=list(csv.reader(stream))
            if len(events)!=128 or any(len(r)!=16 or int(r[0])!=i%2 or
                    r[5]!=f'{bank:02x}{call+(3 if i%2 else 0):04x}' for i,r in enumerate(events)):
                raise ValueError('Missing/wrong column timing events')
            costs=[int(b[4])-int(a[4]) for a,b in zip(events[::2],events[1::2])]
            if any(c<=0 for c in costs):raise ValueError('Invalid elapsed time')
            arms.append(dict(costs=costs,mean=sum(costs)/len(costs)))
        saved=[a-b for a,b in zip(arms[0]['costs'],arms[1]['costs'])]
        results.append(dict(chunk=chunk,arms=arms,saved_min=min(saved),saved_mean=sum(saved)/len(saved),saved_max=max(saved)))
    paths=[Path(__file__),Path('tools/benchmark_report.py'),Path('tools/smoke_libretro.py'),
        Path('tools/snes9x_span_trace.inc'),oracle/'report.json',core]
    report=dict(observer_neutral=True,results=results,
        sources={str(p):sha(p) for p in paths},files={str(p):sha(p) for p in out.iterdir() if p.is_file()},
        scope='448 matched complete column calls. Negative savings for short fallback loops are retained. '
              'No enabled NMI interleaving or game-speed qualification.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps([dict(chunk=r['chunk'],original_mean=r['arms'][0]['mean'],optimized_mean=r['arms'][1]['mean'],
        saved_min=r['saved_min'],saved_mean=r['saved_mean']) for r in results],indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('oracle','core','out'):p.add_argument('--'+name,type=Path,required=True)
    audit(**vars(p.parse_args()))
