"""Execute planar producers and DMA consumers, including immutable snapshots."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import itertools
import json
from pathlib import Path

try:
    from .check_fused_rows import case as row_case, ROWS, attribute_values, ROOT
    from .check_hidden_dma import case as dma_case
except ImportError:
    from check_fused_rows import case as row_case, ROWS, attribute_values, ROOT
    from check_hidden_dma import case as dma_case


def run(core,out):
    out.mkdir(parents=True,exist_ok=False)
    if attribute_values()!=list(range(256)):raise ValueError('Attribute matrix incomplete')
    matrix=list(itertools.product(ROWS,(0,1),(0,16),range(4),(0,64,128,192)))
    def execute(args):
        row,mirror,half,state,seed=args
        row_case(core,out/f'row-{row}-{mirror}-{half}-{state}-{seed}',row,mirror,half,state,
            planar=True,shadow_seed=seed)
    with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(execute,matrix))
    dma=[]
    for state,hidden,chr_bytes,start in itertools.product((0,1,2),(False,True),(0,1024,2048),(0,1,126,127)):
        dma.append(dma_case(core,out/f'dma-{state}-{hidden}-{chr_bytes}-{start}',state,hidden,
            planar=True,chr_bytes=chr_bytes,row_start=start))
    negatives=[]
    for name,kind,old,new in (
        ('overwrite-queued-alias','producer','cmp #1\n    bne :+\n    inc $18','cmp #2\n    bne :+\n    inc $18'),
        ('wrong-high-row','producer','sta a:$4000+group*4,x','sta a:$4002+group*4,x'),
        ('lost-alias-ready','producer','lda #2\n    sta $1D00,x','lda #0\n    sta $1D00,x'),
        ('wrong-high-port','consumer','lda #$19','lda #$18'),
        ('wrong-high-increment','consumer','lda #$80\n    sta $2115','lda #$00\n    sta $2115'),
        ('short-plane-transfer','consumer','lda $1E\n    lsr','lda $1E\n    lsr\n    lsr')):
        directory=out/name;directory.mkdir()
        file='planar_rows.inc' if kind=='producer' else 'planar_dma.inc'
        original=(ROOT/'snes'/file).read_text()
        if original.count(old)!=1:raise ValueError('Ambiguous planar mutant '+name)
        (directory/file).write_text(original.replace(old,new))
        fixture='fused_row_test.asm' if kind=='producer' else 'hidden_dma_test.asm'
        enclosing='native_prepare.asm' if kind=='producer' else 'native_video.asm'
        for item in (fixture,enclosing):(directory/item).write_bytes((ROOT/'snes'/item).read_bytes())
        try:
            if kind=='producer':
                row_case(core,directory/'run',0,0,16,2 if name=='overwrite-queued-alias' else 1,
                    source=directory/fixture,planar=True)
            else:
                dma_case(core,directory/'run',2,True,source=directory/fixture,
                    planar=True,chr_bytes=0,row_start=127)
        except ValueError as error:negatives.append(dict(name=name,error=str(error)))
        else:raise ValueError('Planar mutant passed: '+name)
    digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    report=dict(passed=True,producer_cases=len(matrix),dma_cases=dma,negative_controls=negatives,
        attribute_values=attribute_values(),core_sha256=digest(core),checker_sha256=digest(Path(__file__)),
        source_sha256={str(p.relative_to(ROOT)):digest(p) for p in (
            ROOT/'tools/check_fused_rows.py',ROOT/'tools/check_hidden_dma.py',ROOT/'snes/planar_rows.inc',
            ROOT/'snes/planar_dma.inc',ROOT/'snes/native_prepare.asm',ROOT/'snes/native_video.asm')},
        files={str(p.relative_to(out)):digest(p) for p in out.rglob('*') if p.is_file() and p.suffix in ('.json','.sfc','.ram','.asm','.inc','.log')},
        scope='All 8192 planar staging bytes and 128 row flags, all attribute values and alias states; '
              'real 16KiB VRAM readback across both DMA planes, CHR budgets, queue wrap and forced-blank/visible publication. '
              'Visible transfer may stop at the beam deadline: require a legal nonempty retired prefix and exact independent VRAM. '
              'No gameplay speed, dense scrolling or physical audio verdict.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=True,producer_cases=len(matrix),dma_cases=len(dma),negative_controls=len(negatives))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('core','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();run(a.core,a.out)
