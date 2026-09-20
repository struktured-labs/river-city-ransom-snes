"""Paired same-state FF29 replacement timing on real banked calls."""
import argparse
import csv
import json
import os
from pathlib import Path
import subprocess
import sys
from tools.check_bank_restore import case
from tools.benchmark_report import sha


def run(core,observer,out):
    out.mkdir(parents=True,exist_ok=False)
    values=(0,1,6,7,14,15,254,255)
    samples=[]
    receipts=[]
    sources=[Path(__file__),Path('tools/check_bank_restore.py'),Path('tools/build_native.py'),
             Path('snes/bank_restore.inc'),Path('snes/bank_restore_test.asm')]
    for bank in (1,3,8):
        folder=out/f'bank-{bank}'
        normal=case(core,folder,source_bank=bank,values=values)
        labels={r.split()[2].lstrip('.'):int(r.split()[1],16) for r in (folder/'test.lbl').read_text().splitlines()}
        points=[f'{labels[name]:04x}' for name in ('legacy_call','legacy_done','fast_call','fast_done')]
        env={k:v for k,v in os.environ.items() if not k.startswith('RCR_')}
        env.update(RCR_SPAN_TRACE=str(folder/'spans.csv'),RCR_PROFILE_FIRST='0',RCR_PROFILE_LAST='360',
                   **{f'RCR_SPAN_PC{i}':v for i,v in enumerate(points)})
        subprocess.run([sys.executable,'tools/smoke_libretro.py','--core',str(observer),'--rom',str(folder/'test.sfc'),
            '--kind','adapter','--frames','360','--ram',str(folder/'observed.ram'),'--receipt',str(folder/'observed.json')],
            env=env,capture_output=True,check=True,timeout=30)
        if sha(folder/'observed.ram')!=normal['ram_sha256']:
            raise ValueError('Timing observer changed execution')
        with (folder/'spans.csv').open() as stream:rows=list(csv.reader(stream))
        if len(rows)!=len(values)*4*4:raise ValueError('Incomplete bank timing matrix')
        for i,(fc,fb) in enumerate((fc,fb) for fc in values for fb in (0,7,128,135)):
            group=rows[i*4:i*4+4]
            for j,r in enumerate(group):
                if len(r)!=16 or int(r[0])!=j or int(r[5],16)&65535!=int(points[j],16):
                    raise ValueError('Wrong linked call boundary')
                wanted=0xc0+bank if j in (0,2) else 0xc1+((fc&15)>>1)
                if int(r[5],16)>>16!=wanted:raise ValueError('Wrong caller/return bank')
            clocks=[int(r[4]) for r in group]
            legacy,direct=clocks[1]-clocks[0],clocks[3]-clocks[2]
            samples.append(dict(source_bank=bank,fc=fc,fb=fb,legacy_clocks=legacy,direct_clocks=direct,
                saved_clocks=legacy-direct))
        receipts.append(normal)
        sources += [folder/name for name in ('spans.csv','observed.json','test.lbl','runtime.lbl')]
    result=dict(passed=all(r['saved_clocks']>0 for r in samples),samples=samples,normal_receipts=receipts,
        observer_neutral=True,core_sha256=sha(core),observer_sha256=sha(observer),
        sources={str(p):sha(p) for p in sources},scope='Same initial caller/mapper state; actual banked JSR/RTS '
        'entry and exit clocks, no pending NMI in these timing cases. Whole WRAM equals normal run. '
        'Elapsed includes refresh/events; not full-game speed or interrupt-edge certification.')
    (out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(passed=result['passed'],samples=len(samples),
        savings=[min(r['saved_clocks'] for r in samples),max(r['saved_clocks'] for r in samples)])))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('core','observer','out'):p.add_argument('--'+name,type=Path,required=True)
    run(**vars(p.parse_args()))
