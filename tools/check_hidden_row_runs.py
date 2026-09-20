"""Real-DMA contiguous-run oracle with host-observed hidden-only dispatch."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
import hashlib
import itertools
import json
import os
from pathlib import Path
import subprocess
import sys

try:
    from .check_hidden_dma import case, ROOT
except ImportError:
    from check_hidden_dma import case, ROOT


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def policy(core,observer,out,state,source=None):
    case(core,out,state,True,source=source,row_runs=True,chr_bytes=0)
    symbols={r.split()[2].lstrip('.'):int(r.split()[1],16) for r in (out/'test.lbl').read_text().splitlines()}
    pc=f'{symbols["ready_row_run"]:06x}'
    env={k:v for k,v in os.environ.items() if not k.startswith('RCR_')}
    env.update(RCR_SPAN_PC0=pc,RCR_SPAN_TRACE=str(out/'policy.csv'),RCR_PROFILE_FIRST='0',RCR_PROFILE_LAST='300')
    subprocess.run([sys.executable,str(ROOT/'tools/smoke_libretro.py'),'--core',str(observer),
        '--rom',str(out/'test.sfc'),'--kind','adapter','--frames','300','--ram',str(out/'observed.ram'),
        '--receipt',str(out/'observed.json')],check=True,capture_output=True,env=env,timeout=30)
    if digest(out/'memory.ram')!=digest(out/'observed.ram'):raise ValueError('Observer changed dispatch case WRAM')
    rows=list(csv.reader((out/'policy.csv').open()))
    if any(len(r)!=16 or int(r[0])!=0 or r[5]!=pc for r in rows):raise ValueError('Wrong policy trace point')
    if bool(rows)!=(state==2):raise ValueError('Contiguous-run helper executed outside hidden state 2, or did not execute there')
    return dict(state=state,run_entries=len(rows),observer_equivalent=True)


def run(core,observer,out):
    out.mkdir(parents=True,exist_ok=False)
    matrix=list(itertools.product((0,1,2),(False,True),(0,1024,2048),(0,1,126,127),(None,0,31,127)))
    def execute(args):
        state,hidden,chr_bytes,start,gap=args
        return case(core,out/f'dma-{state}-{hidden}-{chr_bytes}-{start}-{gap}',state,hidden,
            row_runs=True,chr_bytes=chr_bytes,row_start=start,queue_gap=gap)
    with ThreadPoolExecutor(max_workers=4) as pool:cases=list(pool.map(execute,matrix))
    policies=[policy(core,observer,out/f'policy-{s}',s) for s in (0,1,2)]
    original=(ROOT/'snes/native_video.asm').read_text()
    start=original.index('ready_row_run:');end=original.index('pair_ready_row:',start)
    run_source=original[start:end]
    negatives=[]
    for name,old,new,target,state in (
        ('lost-newer-shadow','and #1\n    sta $1D00,x','and #0\n    sta $1D00,x','run',2),
        ('exceeded-byte-budget','cmp $1A','cmp #$FFFF','run',2),
        ('wrong-cursor','adc $08\n    tax\n    rts\nready_row_run:','adc #0\n    tax\n    rts\nready_row_run:','all',2),
        ('state1-policy-leak','cmp #2\n    beq :+\n    jmp pair_ready_row','cmp #1\n    beq :+\n    jmp pair_ready_row','all',1)):
        body=run_source if target=='run' else original
        if body.count(old)!=1:raise ValueError('Ambiguous run mutant '+name)
        mutated=body.replace(old,new)
        if target=='run':mutated=original[:start]+mutated+original[end:]
        directory=out/name;directory.mkdir()
        fixture=directory/'hidden_dma_test.asm';fixture.write_bytes((ROOT/'snes/hidden_dma_test.asm').read_bytes())
        (directory/'native_video.asm').write_text(mutated)
        try:
            if name=='state1-policy-leak':policy(core,observer,directory/'run',state,fixture)
            else:case(core,directory/'run',state,True,source=fixture,row_runs=True,chr_bytes=0,row_start=0)
        except ValueError as error:negatives.append(dict(name=name,error=str(error)))
        else:raise ValueError('Run mutation passed: '+name)
    report=dict(passed=True,cases=cases,policy_cases=policies,negative_controls=negatives,
        core_sha256=digest(core),observer_sha256=digest(observer),checker_sha256=digest(Path(__file__)),
        source_sha256={str(p.relative_to(ROOT)):digest(p) for p in (ROOT/'snes/native_video.asm',ROOT/'snes/hidden_dma_test.asm',ROOT/'tools/check_hidden_dma.py')},
        files={str(p.relative_to(out)):digest(p) for p in out.rglob('*') if p.is_file() and p.suffix in ('.sfc','.ram','.json','.asm','.csv','.lbl','.log')},
        scope='Real 16KiB VRAM readback, all queued generations/requirements, CHR/byte budgets, ring boundaries and unready holes. '
              'Visible publication must retire a legal prefix before the beam deadline. Hidden-only dispatch is host-observed '
              'with full-WRAM normal-core controls. Does not certify full-game speed or acoustic fidelity.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=True,cases=len(cases),policies=len(policies),mutants=len(negatives))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('core','observer','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();run(a.core,a.observer,a.out)
