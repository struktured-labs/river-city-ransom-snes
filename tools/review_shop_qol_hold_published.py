"""Use fully published original dialogue, not a shadow buffer ahead of VRAM."""
import json
from pathlib import Path
import shutil

import numpy as np

from tools.benchmark_report import sha
from tools.review_shop_qol_hold import pixels


def build(previous,out):
    if out.exists():raise ValueError('Fresh output required')
    report=json.loads((previous/'report.json').read_text())
    for p,digest in report['sources'].items():
        if sha(Path(p))!=digest:raise ValueError('Changed source '+p)
    for name,digest in report['artifacts'].items():
        if sha(previous/name)!=digest:raise ValueError('Changed artifact')
    selections=[]
    for result in report['held_results']:
        case=result['case'];i=result['purchase']-1
        original=Path('build')/('shop-qol-teacap-feedback-snes-02' if case=='held_tea' else 'shop-qol-pancakes-feedback-snes-01')
        candidate=Path('build')/('shop-qol-teacap-hold-snes-03' if case=='held_tea' else 'shop-qol-pancakes-hold-snes-01')
        observations=json.loads((original/'shop-qol-amounts.json').read_text())['snapshots']
        receipt=json.loads((original/'capture.json').read_text())
        segments={s['name']:s for s in receipt['segments']}
        considered=[];selected=None
        for snap in observations:
            if snap['dialogue_lines'][1]!=result['text']:continue
            phase=snap['phase'];seg=segments[phase]
            for ext,key in (('png','screenshot_sha256'),('nametable','nametable_snapshot_sha256'),('vram','vram_snapshot_sha256')):
                if sha(original/(phase+'.'+ext))!=seg[key]:raise ValueError('Changed checkpoint')
            table=(original/(phase+'.nametable')).read_bytes();vram=(original/(phase+'.vram')).read_bytes()
            pending=[j for j in range(24*32,28*32) if table[j]!=vram[(0x2000+j)*2]]
            considered.append(dict(phase=phase,pending_dialogue_tiles=pending))
            if not pending:
                selected=snap;break
        if selected is None:raise ValueError('No fully published original text')
        mismatch=int(np.any(pixels(original/(selected['phase']+'.png'))!=pixels(candidate/f'food_{i}_held_result.png'),axis=2).sum())
        selections.append(dict(case=case,purchase=i+1,considered=considered,
            selected_phase=selected['phase'],pixel_mismatches=mismatch))
    gates=dict(report['gates'])
    gates['all_actual_amounts_preserved_and_dismissals_work']=(
        all(r['stat_and_money_match_untouched_parent'] and r['dialogue_held_last_120_frames'] for r in report['held_results'])
        and all(s['pixel_mismatches']==0 for s in selections))
    # Recheck the actual returned state, not a copied optimistic flag.
    for folder,count in [('shop-qol-teacap-hold-snes-03',13),('shop-qol-pancakes-hold-snes-01',2)]:
        base=Path('build')/folder;r=json.loads((base/'capture.json').read_text());segments={s['name']:s for s in r['segments']}
        for i in range(count):
            phase=f'food_{i}_returned';path=base/(phase+'.ram')
            if sha(path)!=segments[phase]['ram_snapshot_sha256'] or path.read_bytes()[0x688]!=8:
                raise ValueError('Final confirmation did not return to shop')
    sources=dict(report['sources'])
    for p in (Path(__file__),previous/'report.json'):sources[str(p)]=sha(p)
    out.mkdir()
    for name in report['artifacts']:shutil.copy2(previous/name,out/name)
    updated=dict(report,passed=all(gates.values()),gates=gates,sources=sources,
        publication_selections=selections,
        previous_failed_pixel_audit=str(previous),
        reference_policy='Earliest exact original message whose full dialogue shadow is published in VRAM. '
          'Selection uses tile publication, never pixel similarity. All earlier unready checkpoints and '
          'their pending tiles are retained. No frame-cadence equivalence claim or image masking.')
    (out/'report.json').write_text(json.dumps(updated,indent=2)+'\n')
    page=(previous/'index.html').read_text().replace('<h1>','<p>Reference glyph checks require the full original dialogue to reach VRAM; '
        'earlier shadow-only checkpoints and the failed first comparison remain recorded.</p><h1>',1)
    (out/'index.html').write_text(page)
    print(json.dumps(dict(passed=updated['passed'],gates=gates,output=str(out)),indent=2))
    return updated['passed']


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('previous','out'):p.add_argument('--'+key,type=Path,required=True)
    raise SystemExit(0 if build(**vars(p.parse_args())) else 1)
