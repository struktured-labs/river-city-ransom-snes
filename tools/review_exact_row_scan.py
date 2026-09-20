"""Matched encounter evidence: reject faster text if it delays the playfield."""
import argparse
from collections import Counter
import json
from pathlib import Path
import shutil
import time

import numpy as np
from PIL import Image

from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha
from tools.review_row_publication import generations


def load(root):
    report = bound_report(root/'report.json')
    for p,h in report['artifacts'].items():
        if sha(root/p) != h: raise ValueError('Changed replay artifact')
    if not report['same_state_comparison_valid']:
        raise ValueError('Invalid restored experiment')
    rows = json.loads((root/'timeline.json').read_text())
    samples = json.loads((root/'row-publication.json').read_text())
    if len(rows) != len(samples) or len(rows) != report['replayed_frames']:
        raise ValueError('Incomplete restored window')
    return report, rows, samples


def publication_gate(before, after):
    key = lambda e: (e['row'], e['col'], e['previous'], e['value'], e['source_frame'])
    old, new = {key(e):e for e in before}, {key(e):e for e in after}
    exact = old.keys() == new.keys()
    missing = [dict(identity=k, arm='trial') for k in old.keys()-new.keys()]
    missing += [dict(identity=k, arm='parent') for k in new.keys()-old.keys()]
    comparisons = []
    for k in old.keys() & new.keys():
        a,b = old[k],new[k]
        passed = b['status'] == 'published' and a['status'] == 'published' and b['vram_latency'] <= a['vram_latency']
        comparisons.append(dict(identity=k, before=a, after=b, nonregression=passed))
    comparisons.sort(key=lambda x:x['identity'])
    return dict(same_sources=exact, missing=missing, comparisons=comparisons,
                nonregression=bool(old) and exact and all(c['nonregression'] for c in comparisons))


def compare(control, trial):
    cp,a,sa = load(control); tp,b,sb = load(trial)
    if not cp['passed'] or tp.get('initial_full_state') != cp['initial_full_state']:
        raise ValueError('Unqualified control or different initial CPU/WRAM/VRAM')
    if [x['frame'] for x in a] != [x['frame'] for x in b]:
        raise ValueError('Different replay coverage')
    all_differences, pictures, ram_changes = [], [], []
    playfield_changes = []; inputs_equal = True; counters_equal = True; camera_equal = True
    for x,y in zip(a,b):
        frame=x['frame']
        fields=sorted(k for k in set(x)|set(y) if x.get(k)!=y.get(k))
        if fields: all_differences.append(dict(frame=frame,fields=fields))
        inputs_equal &= (x['input_requested']==y['input_requested']==x['input_delivered']==y['input_delivered'])
        ra,rb = [bytes.fromhex(z['game_ram_hex']) for z in (x,y)]
        na,nb = [bytes.fromhex(z['native_ram_hex']) for z in (x,y)]
        changes=[dict(address=i,before=p,after=q) for i,(p,q) in enumerate(zip(ra,rb)) if p!=q]
        if changes: ram_changes.append(dict(frame=frame,bytes=changes))
        counters_equal &= ra[0x52b]==rb[0x52b] and na[4:6]==nb[4:6]
        camera_equal &= ra[0xf6]==rb[0xf6] and ra[0x3d]==rb[0x3d] and na[0x94:0x99]==nb[0x94:0x99]
        if x['video_sha256'] != y['video_sha256']:
            pixels=[np.array(Image.open(root/z['frame_image']).convert('RGB')) for root,z in ((control,x),(trial,y))]
            mask=np.any(pixels[0]!=pixels[1],axis=2); yy,xx=np.where(mask)
            if not len(xx): raise ValueError('Different pixel hash but no picture difference')
            picture=dict(frame=frame,pixels=int(mask.sum()),bbox=[int(xx.min()),int(yy.min()),int(xx.max())+1,int(yy.max())+1],
                playfield_pixels=int(mask[32:192].sum()))
            pictures.append(picture)
            if picture['playfield_pixels']: playfield_changes.append(picture)
    source_equal = [s['sprite_source'] for s in sa] == [s['sprite_source'] for s in sb]
    stage_equal = [s['sprite_staging'] for s in sa] == [s['sprite_staging'] for s in sb]
    events = {str(r): publication_gate(generations(sa,r),generations(sb,r)) for r in (2,25)}
    return dict(frames=len(a),first_frame=a[0]['frame'],last_frame=a[-1]['frame'],publication=events,
        gates=dict(same_initial_full_state=True,inputs_equal=inputs_equal,game_nmi_counters_equal=counters_equal,
                   cameras_equal=camera_equal,sprite_source_equal=source_equal,sprite_staging_equal=stage_equal,
                   playfield_pixels_equal=not playfield_changes),
        all_primary_differences=all_differences,all_picture_differences=pictures,all_game_ram_differences=ram_changes,
        playfield_differences=playfield_changes,control_seconds=cp['seconds'],trial_seconds=tp['seconds'],
        initial_generation_left_censored=True,
        scope='Full images and all primary field/RAM differences retained. The fixed y32..191 playfield '
              'comparison is a narrow output tradeoff check, NOT a masked whole-image equality verdict. '
              'Counter/camera samples are not instruction timing or a full-game speed certificate.')


def review(out):
    started=time.monotonic()
    if out.exists(): raise ValueError('Fresh report required')
    control=[Path('build/row-resume-control-3449'),Path('build/row-resume-dialogue-control-3451')]
    variants=dict(unbounded128=['row-resume-trial-3450','row-resume-dialogue-trial-3452'],
        bounded128=['row-resume-bounded-3454','row-resume-dialogue-bounded-3455'],
        bounded64=['row-resume-bounded64-3457','row-resume-dialogue-bounded64-3460'],
        unbounded64=['row-resume-half-3459','row-resume-dialogue-half-3461'])
    sources={}; result={}; cards=[]; table=[]
    out.mkdir()
    bound_report(Path('build/row-checkpoints-3448/checkpoint-report.json'))
    for root in control:
        report,_,_=load(root); sources.update(report['sources']);sources[str(root/'report.json')]=sha(root/'report.json')
    for label, dirs in variants.items():
        roots=[Path('build')/d for d in dirs]
        windows={name:compare(c,t) for name,c,t in zip(('health','dialogue'),control,roots)}
        result[label]=windows
        health=[p for p in windows['health']['publication']['2']['comparisons'] if p['identity'][1]==9]
        if len(health)!=1: raise ValueError('Ambiguous health update')
        h=health[0]['after']; windows['health_target_le_3']=h['status']=='published' and h['vram_latency']<=3
        glyphs=windows['dialogue']['publication']['25']['comparisons']
        table.append(f'<tr><td>{label}</td><td>{h["vram_latency"]}</td>'
            f'<td>{[p["after"]["vram_latency"] for p in glyphs]}</td>'
            f'<td>{windows["health"]["gates"]["playfield_pixels_equal"] and windows["dialogue"]["gates"]["playfield_pixels_equal"]}</td></tr>')
        for root in roots:
            proof,_,_=load(root);sources.update(proof['sources']);sources[str(root/'report.json')]=sha(root/'report.json')
    # Show exact same frames across the source-qualified comparison, not retimed
    # views. Include the rejected full-scan actor delay and a dialogue example.
    for f,window in ((8244,0),(8246,0),(5995,1)):
        cards.append(f'<h3>Exact frame {f}</h3><div class="grid">')
        for label,root in [('parent',control[window])]+[(label,Path('build')/variants[label][window])
                                                     for label in ('unbounded128','bounded128','unbounded64')]:
            _,timeline,_=load(root);row=next(x for x in timeline if x['frame']==f)
            path=root/row['frame_image'];sources[str(path)]=sha(path)
            filename=f'{f}-{label}.png';shutil.copyfile(path,out/filename)
            cards.append(f'<figure><img src="{filename}"><figcaption>{label}</figcaption></figure>')
        cards.append('</div>')
    controls=dict(faster_text_with_playfield_delay_rejected=not result['unbounded128']['health']['gates']['playfield_pixels_equal'],
                  bounded_scan_dialogue_regression_rejected=not result['bounded128']['dialogue']['publication']['25']['nonregression'])
    if not all(controls.values()): raise ValueError('Actual failing variants escaped tradeoff gates')
    selected=result['unbounded64']
    selected['focused_improvement']=all(all(selected[w]['gates'].values()) for w in ('health','dialogue')) and all(
        selected[w]['publication'][r]['nonregression'] for w,r in (('health','2'),('dialogue','25')))
    report=dict(variants=result,negative_controls=controls,selected='unbounded64',
                passed=selected['focused_improvement'] and selected['health_target_le_3'],
                release_ready=False,hardware_verified=False,sources=sources,scope=__doc__)
    paths=[Path(__file__),Path('tools/review_row_publication.py'),Path('tests/test_exact_row_scan.py'),
           Path('build/row-checkpoints-3448/checkpoint-report.json')]
    sources.update({str(p):sha(p) for p in paths})
    (out/'index.html').write_text(f'''<!doctype html><meta charset="utf-8"><title>Exact-state row scan</title>
<style>body{{background:#14202b;color:#eef;font:17px system-ui;max-width:1200px;margin:25px auto}}a{{color:#9ef}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr)}}figure{{margin:6px}}img{{width:100%;image-rendering:pixelated}}
td,th{{padding:8px;border-bottom:1px solid #456}}</style>
<h1>Exact-state replay: faster text must not cost sprite updates</h1>
<p>Fresh-process controls reproduce uninterrupted video, original RAM, delivered inputs and native PCM exactly.
All variants start with identical full WRAM/VRAM and CPU registers.32 health-window frames and50 dialogue-window frames;
roughly5½ seconds per variant including verification. No console changes.</p>
<p>Parent health delay:7 frames. Parent dialogue delays:3,5,7,5,7,5,5,7,5,7,7 frames.</p>
<table><tr><th>Variant</th><th>Health delay</th><th>11 dialogue glyph delays</th><th>Playfield pixels equal</th></tr>{''.join(table)}</table>
<p>Selected64-entry search improves both text windows without changing any playfield pixels, sprite source/staging,
sampled game/NMI counters, camera values or delivered inputs. Full images/state/audio still differ; all differences remain in JSON.
The old3-frame health target remains unmet. Not release-ready; long-route audio/DMA/sprite qualification remains separate.</p>
{''.join(cards)}<p><a href="report.json">Complete differences, generation chains, negative controls and source hashes</a>.</p>
<p>Read-only checks follow the romhack-test-loop skill: preserve failed variants, qualify restoration,
and pair the symptom fix with a visible-output tradeoff check.</p>''')
    if any(sha(Path(p))!=h for p,h in sources.items()): raise ValueError('Changed report source')
    report['seconds']=time.monotonic()-started
    report['artifacts']={p.name:sha(p) for p in out.iterdir() if p.is_file()}
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=report['passed'],focused_improvement=selected['focused_improvement'],
                         negative_controls=controls,seconds=report['seconds'])))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True)
    review(**vars(p.parse_args()))
