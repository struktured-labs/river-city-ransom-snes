"""FastROM publisher cost for equal-byte old pairs versus contiguous runs."""
import argparse
import csv
import json
import os
from pathlib import Path
import subprocess
import sys

try:
    from .check_hidden_dma import case, ROOT
    from .check_hidden_row_runs import digest
except ImportError:
    from check_hidden_dma import case, ROOT
    from check_hidden_row_runs import digest


def run(core,control,out):
    out.mkdir(parents=True,exist_ok=False)
    comparisons=[]
    for chr_bytes in (0,1024,2048):
        arms={};semantic=[]
        for name,enabled in (('pairs',False),('runs',True)):
            directory=out/f'chr-{chr_bytes}-{name}'
            result=case(control,directory,2,True,chr_bytes=chr_bytes,row_runs=enabled,fastrom=True)
            ram=(directory/'memory.ram').read_bytes()
            # Common readback covers every transferred tile in these equal-size
            # row-zero batches. Compare generation flags independently too.
            semantic.append((ram[0x8000:0xb000],ram[0x1d00:0x1d80],ram[0x1e80:0x1f00],ram[0x1c74]))
            symbols={r.split()[2].lstrip('.'):int(r.split()[1],16) for r in (directory/'test.lbl').read_text().splitlines()}
            points=[f'c0{symbols[k]:04x}' for k in ('native_video','transition_ready')]
            env={k:v for k,v in os.environ.items() if not k.startswith('RCR_')}
            env.update(RCR_SPAN_PC0=points[0],RCR_SPAN_PC1=points[1],RCR_SPAN_TRACE=str(directory/'spans.csv'),
                RCR_PROFILE_FIRST='0',RCR_PROFILE_LAST='300')
            subprocess.run([sys.executable,str(ROOT/'tools/smoke_libretro.py'),'--core',str(core),
                '--rom',str(directory/'test.sfc'),'--kind','adapter','--frames','300','--ram',str(directory/'observed.ram'),
                '--receipt',str(directory/'observed.json')],check=True,capture_output=True,env=env,timeout=30)
            if digest(directory/'memory.ram')!=digest(directory/'observed.ram'):raise ValueError('Observer changed WRAM')
            rows=list(csv.reader((directory/'spans.csv').open()))
            if len(rows)!=2 or any(len(r)!=16 or int(r[0])!=i or r[5]!=points[i] for i,r in enumerate(rows)):
                raise ValueError('Missing linked publisher span')
            clocks=int(rows[1][4])-int(rows[0][4])
            if clocks<=0:raise ValueError('Nonmonotonic publisher span')
            arms[name]=dict(clocks=clocks,oracle=result,observer_equivalent=True,
                files={p.name:digest(p) for p in directory.iterdir() if p.suffix in ('.json','.sfc','.ram','.csv','.lbl')})
        if semantic[0]!=semantic[1]:raise ValueError('Different actual publication results between timing arms')
        comparisons.append(dict(chr_bytes=chr_bytes,arms=arms,
            saved_master_clocks=arms['pairs']['clocks']-arms['runs']['clocks']))
    report=dict(passed=all(r['saved_master_clocks']>0 for r in comparisons),comparisons=comparisons,
        core_sha256=digest(core),control_sha256=digest(control),checker_sha256=digest(Path(__file__)),
        scope='Native-video entry through completed VRAM batches before transition/final OAM/CGRAM service. '
              'FastROM enabled, equal 4096-byte total budgets and identical VRAM/generation flags. '
              'Elapsed clocks include real DMA; each arm has full-WRAM observer control. Not a game-speed ratio.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=report['passed'],savings=[dict(chr_bytes=r['chr_bytes'],clocks=r['saved_master_clocks']) for r in comparisons])))
    return report['passed']


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('core','control','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();raise SystemExit(0 if run(a.core,a.control,a.out) else 1)
