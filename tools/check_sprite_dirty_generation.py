"""Execute compact sprite-generation marking and independent corruption controls."""
import argparse
import json
from pathlib import Path

from tools.check_sprite_delta import check
from tools.check_video import check as pixels
from tools.benchmark_report import sha


def run(core,out):
    out.mkdir(parents=True,exist_ok=False)
    hashes={str(p):sha(p) for p in (Path(__file__),Path('tools/check_sprite_delta.py'),
        Path('tools/check_video.py'),Path('snes/native_prepare.asm'),Path('snes/native_video.asm'),
        Path('snes/sprite_delta.inc'),Path('snes/video_test.asm'),core)}
    good=check(core,out/'good',dirty_final_dma=True)
    if not good['passed']:
        raise ValueError('Production generation/ABI oracle failed')
    mutations=(
        ('missing-mark',('    sta $1CEE','    nop\n    nop\n    nop')),
        ('missing-counter-initialization',('    ldy #0','    nop\n    nop\n    nop')),
        ('lost-pending',('    tya\n    beq :+','    tya\n    stz $1CEE\n    beq :+')),
        ('lost-y',('    ply','    plx')),
        ('ignored-attribute-count',('    sta $5602 + sprite*4\n    and #$00FF\n    tax\n    sep #$20\n    .a8\n.ifdef EXPERIMENTAL_DIRTY_FINAL_DMA\n    iny',
            '    sta $5602 + sprite*4\n    and #$00FF\n    tax\n    sep #$20\n    .a8\n.ifdef EXPERIMENTAL_DIRTY_FINAL_DMA\n    nop')))
    negatives=[]
    for name,mutation in mutations:
        result=check(core,out/name,mutation,dirty_final_dma=True)
        if result['passed']:
            raise ValueError('Generation mutant survived: '+name)
        negatives.append(dict(name=name,report=result))
    pixels(core,out/'pixels',dirty_final_dma=True,sprite_delta=True,oam_compare_test=True)
    if hashes!={str(p):sha(p) for p in map(Path,hashes)}:
        raise ValueError('Sources changed during generation oracle')
    report=dict(passed=True,positive=good,negatives=negatives,sources=hashes,
        artifacts={str(p):sha(p) for p in (out/'pixels').iterdir() if p.is_file()},
        scope='27 successive full544-byte OAM/snapshot comparisons and generation-latch checks; '
              'all-changed128-word case, isolated byte edits, unchanged source, initial and '
              'pattern invalidation, pending-latch preservation, Y/DB/DP/width restoration. '
              'Five executed mutations and complete production producer/publisher pixel fixture. '
              'Not whole-game timing or audio certification.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=True,cases=good['cases'],mutants=len(negatives))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('core','out'):p.add_argument('--'+name,type=Path,required=True)
    run(**vars(p.parse_args()))
