"""Observe exact palette-copy cost and guarded-path selection in oracled ROMs."""
import argparse
import csv
import json
import os
from pathlib import Path
import subprocess
import sys

from tools.benchmark_report import sha


def run(oracle,observer,out):
    report=json.loads((oracle/'report.json').read_text())
    if not report['passed'] or len(report['cases'])!=59:raise ValueError('Need complete palette oracle')
    out.mkdir(parents=True,exist_ok=False);comparisons=[]
    for index,case in enumerate(report['cases']):
        root=oracle/f'case-{index:03d}'
        runtime=root/'runtime.lbl'
        if sha(runtime)!=report['files'][str(runtime.relative_to(oracle))]:raise ValueError('Changed runtime labels')
        symbols={r.split()[2].lstrip('.'):int(r.split()[1],16) for r in runtime.read_text().splitlines()}
        owned=symbols['@owned']
        if not symbols['palette_copy_loop']<owned<symbols['dispatch_write']:
            raise ValueError('Ambiguous owned-path symbol')
        arms=[]
        for fast in (0,1):
            folder=root/str(fast);target=out/f'{index:03d}-{fast}';target.mkdir()
            for name in ('test.sfc','memory.ram'):
                if sha(folder/name)!=report['files'][str((folder/name).relative_to(oracle))]:
                    raise ValueError('Changed oracle artifacts')
            points=['c7e477','c7e482',f'c7{owned:04x}']
            env={k:v for k,v in os.environ.items() if not k.startswith('RCR_')}
            env.update(RCR_SPAN_TRACE=str(target/'spans.csv'),RCR_PROFILE_FIRST='0',RCR_PROFILE_LAST='300',
                       **{f'RCR_SPAN_PC{i}':p for i,p in enumerate(points)})
            subprocess.run([sys.executable,'tools/smoke_libretro.py','--core',str(observer),
                '--rom',str(folder/'test.sfc'),'--kind','adapter','--frames','300',
                '--ram',str(target/'memory.ram'),'--receipt',str(target/'receipt.json')],
                env=env,capture_output=True,check=True,timeout=30)
            if sha(target/'memory.ram')!=sha(folder/'memory.ram'):raise ValueError('Observer changed WRAM')
            with (target/'spans.csv').open() as source:rows=list(csv.reader(source))
            if not rows or any(len(r)!=16 or r[5]!=points[int(r[0])] for r in rows):
                raise ValueError('Wrong trace boundaries')
            end=[r for r in rows if r[0]=='1'];entered=[r for r in rows if r[0]=='2']
            if (rows[0][0]!='0' or len(end)!=1 or rows[-1]!=end[0]
                    or len(entered)!=int(fast and case['eligible'])):
                raise ValueError('Wrong copy completion or guarded-path selection')
            clocks=int(end[0][4])-int(rows[0][4])
            if clocks<=0:raise ValueError('Nonmonotonic clocks')
            arms.append(dict(clocks=clocks,owned_entries=len(entered),
                spans_sha256=sha(target/'spans.csv'),ram_sha256=sha(target/'memory.ram')))
        comparisons.append(dict(case=index,eligible=case['eligible'],options=case['options'],
            before=arms[0],after=arms[1],saved_clocks=arms[0]['clocks']-arms[1]['clocks']))
    result=dict(passed=all(c['saved_clocks']>0 for c in comparisons if c['eligible']),
        observer_equivalent=True,comparisons=comparisons,
        sources={str(p):sha(p) for p in (oracle/'report.json',observer,Path(__file__))},
        scope='Exact E477 to E482 copy spans and fast-path entry count in all 59 paired '
              'oracled ROMs. Unsupported states must never enter the batch; fallback '
              'overhead is reported, not omitted. Full WRAM observer neutrality per ROM. '
              'Not actual game timing, analog audio or pending-NMI injection coverage.')
    (out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    eligible=[c['saved_clocks'] for c in comparisons if c['eligible']]
    fallback=[c['saved_clocks'] for c in comparisons if not c['eligible']]
    print(json.dumps(dict(passed=result['passed'],cases=len(comparisons),
        eligible_savings=[min(eligible),max(eligible)],fallback_savings=[min(fallback),max(fallback)])))
    return result['passed']


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('oracle','observer','out'):p.add_argument('--'+name,type=Path,required=True)
    raise SystemExit(0 if run(**vars(p.parse_args())) else 1)
