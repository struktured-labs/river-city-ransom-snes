"""Measure original and unrolled coordinate loops at identical linked boundaries."""
import argparse
from collections import Counter
import csv
import json
import os
from pathlib import Path
import subprocess

from tools.benchmark_report import sha


def run(oracle,core,out,position=False):
    qualified=json.loads((oracle/'report.json').read_text())
    count_key='offset_pairs' if position else 'low_byte_pairs'
    entry='eeee' if position else 'ef11'
    frames='1600' if position else '1400'
    if not qualified['passed'] or qualified[count_key]!=65536:raise ValueError('Unqualified coordinate oracle')
    for p,h in qualified['sources'].items():
        if sha(Path(p))!=h:raise ValueError('Changed coordinate oracle source')
    out.mkdir(parents=True,exist_ok=False)
    results=[]
    for chunk in (0,1,7,31):
        arms=[]
        for optimized in (0,1):
            folder=oracle/f'chunk-{chunk:02d}-{optimized}'
            for p,h in qualified['cases'][chunk]['arms'][optimized].items():
                if sha(Path(p))!=h:raise ValueError('Changed coordinate fixture')
            base=out/f'{chunk}-{optimized}';trace=base.with_suffix('.csv');ram=base.with_suffix('.ram')
            bank=0xc1+chunk%8
            env={k:v for k,v in os.environ.items() if not k.startswith('RCR_')}
            env.update(RCR_SPAN_TRACE=str(trace),RCR_PROFILE_FIRST='0',RCR_PROFILE_LAST=frames,
                RCR_SPAN_PC0=f'{bank:02x}'+entry,RCR_SPAN_PC1=f'{bank:02x}ef26')
            subprocess.run(['python3','tools/smoke_libretro.py','--core',str(core),'--rom',str(folder/'test.sfc'),
                '--kind','adapter','--frames',frames,'--ram',str(ram),'--receipt',str(base.with_suffix('.json'))],
                env=env,check=True,capture_output=True,timeout=60)
            if sha(ram)!=sha(folder/'memory.ram'):raise ValueError('Timing observer changed complete WRAM')
            events=list(csv.reader(trace.open()))
            if len(events)!=4096 or any(len(r)!=16 or int(r[0])!=i%2 or
                    r[5]!=f'{bank:02x}'+(entry if i%2==0 else 'ef26') for i,r in enumerate(events)):
                raise ValueError('Incomplete/wrong coordinate timing points')
            costs=[int(b[4])-int(a[4]) for a,b in zip(events[::2],events[1::2])]
            if any(n<=0 for n in costs):raise ValueError('Invalid coordinate clocks')
            arms.append(dict(costs=costs,histogram=dict(Counter(costs)),mean=sum(costs)/len(costs)))
        saved=[a-b for a,b in zip(arms[0]['costs'],arms[1]['costs'])]
        results.append(dict(chunk=chunk,arms=arms,saved_min=min(saved),saved_mean=sum(saved)/len(saved),saved_max=max(saved)))
    paths=[Path(__file__),Path('tools/benchmark_report.py'),Path('tools/smoke_libretro.py'),
        Path('tools/snes9x_span_trace.inc'),oracle/'report.json',core]
    report=dict(passed=all(r['saved_min']>0 for r in results),observer_neutral=True,results=results,
        sources={str(p):sha(p) for p in paths},files={str(p):sha(p) for p in out.iterdir() if p.is_file()},
        scope=f'Actual {entry.upper()} entry to EF26 continuation, includes trampoline overhead and refresh/events. '
              '8192 matched cases across four matrix chunks. Not an overall game-speed or latency verdict.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps([dict(chunk=r['chunk'],saved_min=r['saved_min'],saved_mean=r['saved_mean'],
        original_mean=r['arms'][0]['mean'],optimized_mean=r['arms'][1]['mean']) for r in results],indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('oracle','core','out'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--position',action='store_true')
    a=p.parse_args();run(a.oracle,a.core,a.out,a.position)
