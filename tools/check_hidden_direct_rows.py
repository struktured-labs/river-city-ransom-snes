"""Actual VRAM oracle for hidden direct rows, including immutable alias states."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import itertools
import json
from pathlib import Path

try:
    from .check_fused_rows import case, ROOT, ROWS, attribute_values
    from .check_hidden_row_runs import digest
except ImportError:
    from check_fused_rows import case, ROOT, ROWS, attribute_values
    from check_hidden_row_runs import digest


def run(core,out,full=False):
    out.mkdir(parents=True,exist_ok=False)
    sources=(Path(__file__),ROOT/'tools/check_fused_rows.py',
        ROOT/'snes/hidden_direct_rows.inc',ROOT/'snes/native_prepare.asm',ROOT/'snes/fused_row_test.asm',
        ROOT/'snes/hidden_direct_probe_setup.inc',ROOT/'snes/hidden_direct_probe_readback.inc')
    source_hashes={str(p.relative_to(ROOT)):digest(p) for p in sources}
    matrix=list(itertools.product(ROWS if full else (0,2,33,61,64,98,125),(0,1),(0,16),range(4),
        (0,64,128,192) if full else (0,)))
    def execute(args):
        row,mirror,half,state,seed=args
        case(core,out/f'row-{row}-{mirror}-{half}-{state}-{seed}',row,mirror,half,state,
            shadow_seed=seed,direct_state=2,fastrom=True)
    with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(execute,matrix))
    for transition,state in itertools.product((0,1),range(4)):
        case(core,out/f'policy-{transition}-{state}',0,0,0,state,direct_state=transition,fastrom=True)
    negatives=[];source=(ROOT/'snes/hidden_direct_rows.inc').read_text()
    for name,state,old,new in (
        ('queued-alias-overwrite',2,'cmp #1\n    bne @done','cmp #2\n    bne @done'),
        ('wrong-high-port',1,'lda #$19\n    sta $4301','lda #$18\n    sta $4301'),
        ('missing-forced-blank',1,'lda #$80\n    sta $2100','lda #$0F\n    sta $2100'),
        ('wrong-source-bank',1,'lda #$7F\n    sta $4304','lda #$7E\n    sta $4304'),
        ('wrong-high-table',1,'((attribute & 3) << 2) * $0101','((attribute & 3) << 1) * $0101'),
        ('missing-pattern-selector',1,'    lda $0E\n','    lda #0\n')):
        if source.count(old)!=1:raise ValueError('Ambiguous direct-row mutant '+name)
        directory=out/name;directory.mkdir()
        # The source include is resolved beside native_prepare, before -I paths.
        (directory/'native_prepare.asm').write_bytes((ROOT/'snes/native_prepare.asm').read_bytes())
        (directory/'hidden_direct_rows.inc').write_text(source.replace(old,new))
        fixture=directory/'fused_row_test.asm';fixture.write_bytes((ROOT/'snes/fused_row_test.asm').read_bytes())
        try:case(core,directory/'run',0,0,16,state,source=fixture,direct_state=2,fastrom=True)
        except ValueError as error:negatives.append(dict(name=name,error=str(error)))
        else:raise ValueError('Direct-row mutant passed: '+name)
    if source_hashes!={str(p.relative_to(ROOT)):digest(p) for p in sources}:
        raise ValueError('Sources changed during oracle run; discard and rerun')
    report=dict(passed=True,cases=len(matrix),policy_cases=8,negative_controls=negatives,
        all_attribute_values=attribute_values() if full else None,core_sha256=digest(core),
        sources=source_hashes,
        files={str(p.relative_to(out)):digest(p) for p in out.rglob('*') if p.is_file() and p.suffix in ('.asm','.inc','.sfc','.ram','.json','.lbl','.log')},
        scope='Full actual 8192-byte tilemap VRAM, unchanged queued staging and original NES shadow, all 128 row flags and initial requirements. '
              'Starts during active display with forced blank disabled; states 0/1 must retain the original staged path and leave VRAM untouched. '
              'One-row budget; whole-load budget and timing require separate integration checks.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=True,cases=len(matrix),policy_cases=8,mutants=len(negatives))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('core','out'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--full',action='store_true');a=p.parse_args();run(a.core,a.out,a.full)
