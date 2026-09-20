"""Executed VRAM/ownership oracle for compact hidden attribute indices."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import itertools
import json
from pathlib import Path

from tools.benchmark_report import sha
from tools.check_hidden_high_cache import case, ROOT


def run(core,out,full=False):
    out.mkdir(parents=True,exist_ok=False)
    paths=[Path(__file__),ROOT/'tools/check_hidden_high_cache.py',ROOT/'tools/check_rows.py',
           ROOT/'tools/smoke_libretro.py',*[ROOT/'snes'/p for p in ('hidden_direct_rows.inc',
            'native_prepare.asm','hidden_high_cache_test.asm','hidden_direct_probe_setup.inc',
            'hidden_direct_probe_readback.inc','native_boot.cfg','wram_clear.inc')]]
    sources={str(p):sha(p) for p in paths}
    starts=range(128) if full else (0,1,2,28,29,30,31,32,60,63,64,92,95,96,124,127)
    matrix=list(itertools.product(starts,(0,1),(0,16),(1,2,16),(1,2),(False,True)))
    def execute(item):
        i,(start,mirror,half,budget,calls,dirty_alias)=item
        return case(core,out/f'case-{i:04d}',start=start,mirror=mirror,half=half,budget=budget,
                    calls=calls,dirty_alias=dirty_alias,compact_index=True)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(execute,enumerate(matrix)))
    mutants=[]
    for name,options,old,new in (
        ('wrong-half-index',dict(half=16),'    lsr\n    lsr                     ; pattern',
             '    lsr\n    nop                     ; pattern'),
        ('wrong-quadrant',dict(start=2),'        and #$00F0','        and #$000F'),
        ('missing-index-step',{},'        iny\n.else','        nop\n.else'),
        ('wrong-half-table',dict(half=16),'| half) * $0101','| 0) * $0101'),
        ('stale-cache',dict(calls=2,budget=1),'lda #$FFFF\n    sta $20',
             'nop\n    nop\n    nop\n    nop\n    nop')):
        source='native_prepare.asm' if name=='stale-cache' else 'hidden_direct_rows.inc'
        # Both table pairs must be changed together for this intentional mutant.
        if name=='wrong-half-table':
            old='(((attribute & 3) << 2) | half) * $0101'
            new='(((attribute & 3) << 2) | 0) * $0101'
        args=dict(budget=16,dirty_alias=True,compact_index=True)
        args.update(options)
        try:
            case(core,out/name,**args,mutation=(source,old,new))
        except ValueError as error:
            mutants.append(dict(name=name,error=str(error)))
        else:
            raise ValueError('Unsafe compact index mutant survived: '+name)
    if sources!={str(p):sha(p) for p in paths}:
        raise ValueError('Sources changed during execution')
    report=dict(passed=True,cases=results,mutants=mutants,sources=sources,core_sha256=sha(core),
        scope='Every starting row in full mode, both mirroring/pattern halves, budgets1/2/16, '
              'changed repeated calls and dirty/mixed aliases. Independent full8192-byte actual '
              'VRAM oracle, all row flags/requirements, original shadow and immutable staging, '
              'cursor/budgets. Not full-game timing or physical audio qualification.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=True,cases=len(results),mutants=len(mutants))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('core','out'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--full',action='store_true')
    run(**vars(p.parse_args()))
