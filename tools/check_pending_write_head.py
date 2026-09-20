"""Execute safe write-head palette eligibility across the full command ring."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path

from tools.check_pending_palette import case,ROOT
from tools.benchmark_report import sha


def run(core,out,all_levels=False):
    out.mkdir(parents=True,exist_ok=False)
    files=[ROOT/'snes'/n for n in ('pending_palette.asm','pending_palette_queue.inc',
            'pending_palette_test.asm','native_video.asm')]+[Path(__file__),ROOT/'tools/check_pending_palette.py']
    sources={str(p.relative_to(ROOT)):sha(p) for p in files}
    matrix=[dict(PREVIEW_WRITE_HEAD=1,QUEUE_READ=r,QUEUE_WRITE=(r+6)&63,QUEUE_CONTROL=c)
            for r in range(64) for c in (0,4,127,128,255)]
    matrix += [dict(PREVIEW_WRITE_HEAD=1,QUEUE_READ=r,QUEUE_WRITE=w) for r,w in ((64,0),(0,64),(255,0),(0,255),(255,255))]
    matrix += [dict(PREVIEW_WRITE_HEAD=1,QUEUE_READ=0,QUEUE_WRITE=w,FADE_LEVEL=level)
               for w in (0,6) for level in (1,2,3,4,255)]
    matrix += [dict(PREVIEW_WRITE_HEAD=1,QUEUE_READ=63,QUEUE_WRITE=5,QUEUE_CONTROL=c,
                    INTEGRATED=1,BEAM_LINE=line) for c in (4,128) for line in (240,242,245,260)]
    def execute(item):
        i,options=item;return case(core,out/f'case-{i:03d}',dict(options,ALL_LEVELS=int(all_levels)))
    with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(execute,enumerate(matrix)))
    negatives=[]
    mutations=[
        ('read-head-accepted',dict(QUEUE_READ=0,QUEUE_WRITE=6,QUEUE_CONTROL=128),'bmi @no','nop\n    nop'),
        ('wrong-head-offset',dict(QUEUE_READ=63,QUEUE_WRITE=5,QUEUE_CONTROL=128),'inx\n    inx','inx\n    nop'),
        ('unbounded-read-pointer',dict(QUEUE_READ=64,QUEUE_WRITE=0),'cmp #64\n    bcs @no\n    lda a:$06B7',
            'cmp #64\n    nop\n    nop\n    lda a:$06B7'),
    ]
    if all_levels:
        mutations.append(('late-generation-rejected',dict(QUEUE_READ=0,QUEUE_WRITE=6,FADE_LEVEL=1),
            '.ifndef EXPERIMENTAL_PENDING_PALETTE_ALL_LEVELS','.if 1'))
    else:
        mutations.append(('later-generation-preview',dict(QUEUE_READ=0,QUEUE_WRITE=6,FADE_LEVEL=1),
            'lda a:$0692\n    bne @no','lda a:$0692\n    nop\n    nop'))
    for name,options,old,new in mutations:
        try:case(core,out/name,dict(PREVIEW_WRITE_HEAD=1,ALL_LEVELS=int(all_levels),**options),('pending_palette_queue.inc',old,new))
        except ValueError as error:negatives.append(dict(name=name,error=str(error)))
        else:raise ValueError('Unsafe palette queue mutant survived: '+name)
    if sources!={str(p.relative_to(ROOT)):sha(p) for p in files}:raise ValueError('Sources changed during queue oracle')
    report=dict(passed=True,all_levels=all_levels,cases=results,mutants=negatives,sources=sources,core_sha256=sha(core),
                scope='All 64 ring starts, write/read markers, invalid pointers and integrated real CGRAM timing. '
                'Caller ABI and source/shadow immutability checked by the existing independent palette oracle.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=True,cases=len(results),mutants=len(negatives))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('core','out'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--all-levels',action='store_true')
    run(**vars(p.parse_args()))
