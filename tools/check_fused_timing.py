"""Compare complete row-stage FastROM spans with neutral full-WRAM observers."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

try:
    from .check_fused_rows import case, ROOT
except ImportError:
    from check_fused_rows import case, ROOT


def run(core,control,out,planar=False):
    out.mkdir(parents=True,exist_ok=False)
    digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    comparisons=[]
    for row,mirror,state in ((0,0,1),(2,0,1),(64,0,1),(66,0,1),(0,1,1),(32,1,1),(0,0,2),(0,0,3)):
        arms={}
        for label,enabled in (('copy',False),('fused',True)):
            folder=out/f'row-{row}-mirror-{mirror}-state-{state}-{label}'
            case(control,folder,row,mirror,0,state,enabled=True if planar else enabled,
                 fastrom=True,planar=planar and enabled)
            symbols={r.split()[2].lstrip('.'):int(r.split()[1],16) for r in (folder/'test.lbl').read_text().splitlines()}
            points=[f'c0{symbols[k]:04x}' for k in ('native_prepare','prepare_palette')]
            env={k:v for k,v in os.environ.items() if not k.startswith('RCR_')}
            env.update(RCR_SPAN_TRACE=str(folder/'spans.csv'),RCR_PROFILE_FIRST='0',RCR_PROFILE_LAST='300',
                RCR_SPAN_PC0=points[0],RCR_SPAN_PC1=points[1])
            subprocess.run([sys.executable,str(ROOT/'tools/smoke_libretro.py'),'--core',str(core),
                '--rom',str(folder/'test.sfc'),'--kind','adapter','--frames','300',
                '--ram',str(folder/'observed.ram'),'--receipt',str(folder/'observed.json')],
                check=True,capture_output=True,env=env,timeout=30)
            if digest(folder/'observed.ram')!=digest(folder/'memory.ram'):raise ValueError('Timing observer changed WRAM')
            rows=list(csv.reader((folder/'spans.csv').open()))
            if len(rows)!=2 or any(len(r)!=16 or int(r[0])!=i or r[5]!=points[i] for i,r in enumerate(rows)):
                raise ValueError('Missing exact row-stage entry/exit')
            clocks=int(rows[1][4])-int(rows[0][4])
            if clocks<=0:raise ValueError('Nonmonotonic clock')
            arms[label]=dict(clocks=clocks,observer_equivalent=True,
                files={p.name:digest(p) for p in folder.iterdir() if p.suffix in ('.sfc','.ram','.json','.lbl','.csv')})
        comparisons.append(dict(row=row,mirror=mirror,state=state,arms=arms,
            saved_master_clocks=arms['copy']['clocks']-arms['fused']['clocks']))
    report=dict(passed=all(c['saved_master_clocks']>0 for c in comparisons if c['state']==1),
        arms_meaning={'copy':'fused-interleaved' if planar else 'separate-alias-copy',
                      'fused':'planar' if planar else 'fused-interleaved'},
        comparisons=comparisons,core_sha256=digest(core),control_sha256=digest(control),
        checker_sha256=digest(Path(__file__)),
        scope='Complete one-row stage before palette preparation, FastROM enabled. Includes helper overhead/events. '
              'Dirty aliases must improve; queued-alias overhead is separately retained, not omitted. Full WRAM observer controls per arm.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=report['passed'],savings=[{k:v for k,v in c.items() if k!='arms'} for c in comparisons]),indent=2))
    return report['passed']


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('core','control','out'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--planar',action='store_true',help='Compare planar rows against fused interleaved baseline')
    a=p.parse_args();raise SystemExit(0 if run(a.core,a.control,a.out,a.planar) else 1)
