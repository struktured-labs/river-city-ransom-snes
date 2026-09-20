"""Candidate3502 exact-state HUD/dialogue guards; retain unmet three-frame health target."""
import argparse
import html
import json
from pathlib import Path
import shutil

from tools.benchmark_report import sha
from tools.review_exact_row_scan import compare,load


def review(out):
    if out.exists():raise ValueError('Fresh report required')
    sources={};windows={};roots={}
    for name,c,t in [('health','row-resume-control-3449','transition-direct-health-3519'),
                     ('dialogue','row-resume-dialogue-control-3451','transition-direct-dialogue-3520')]:
        control,trial=Path('build')/c,Path('build')/t;roots[name]=(control,trial)
        windows[name]=compare(control,trial)
        for root in (control,trial):
            proof,_,_=load(root);sources.update(proof['sources']);sources[str(root/'report.json')]=sha(root/'report.json')
    health=windows['health']['publication']['2']['comparisons']
    target=[p for p in health if p['identity'][1]==9]
    if len(target)!=1:raise ValueError('Ambiguous health generation')
    target=target[0];glyphs=windows['dialogue']['publication']['25']['comparisons']
    checks=dict(exact_guards=all(all(w['gates'].values()) for w in windows.values()),
        health_nonregression=windows['health']['publication']['2']['nonregression'],
        dialogue_nonregression=windows['dialogue']['publication']['25']['nonregression'],
        health_target_le_3=target['after']['status']=='published' and target['after']['vram_latency']<=3)
    summary=dict(checks=checks,health_source=target['identity'],health_before_after=[target['before']['vram_latency'],target['after']['vram_latency']],
        dialogue_before_after=[[p['before']['vram_latency'],p['after']['vram_latency']] for p in glyphs])
    out.mkdir();cards=[]
    for f in (8246,8247):
        for label,root in zip(('audio-parent3408','candidate3502'),roots['health']):
            _,rows,_=load(root);row=next(r for r in rows if r['frame']==f);src=root/row['frame_image']
            filename=f'{label}-{f}.png';shutil.copyfile(src,out/filename);sources[str(src)]=sha(src)
            cards.append(f'<figure><img src="{filename}"><figcaption>{label}, frame {f}</figcaption></figure>')
    scope=(__doc__+' Both fresh replays start with identical CPU/full WRAM/VRAM against controls authenticated to '
        'uninterrupted3408 execution. All later primary audio/state/picture differences remain recorded. '
        'Playfield equality is a narrow tradeoff check, not whole-frame equality. No alignment or physical deployment.')
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Transition candidate row guards</title>'
        '<style>body{background:#101821;color:#eef;font:17px system-ui;max-width:1100px;margin:30px auto}a{color:#9df}pre{white-space:pre-wrap}.grid{display:grid;grid-template-columns:1fr 1fr}img{width:384px;image-rendering:pixelated}</style>'
        '<h1>HUD/dialogue guards — health target still unmet</h1><p>'+html.escape(scope)+'</p><pre>'+html.escape(json.dumps(summary,indent=2))+
        '</pre><p><a href="report.json">All primary differences and sources</a> · <a href="../transition-display-summary-3518/">Full-route qualification</a></p>'
        '<div class="grid">'+''.join(cards)+'</div>')
    for p in (Path(__file__),Path('tools/review_exact_row_scan.py'),Path('tools/review_row_publication.py')):sources[str(p)]=sha(p)
    if any(sha(Path(p))!=h for p,h in sources.items()):raise ValueError('Changed binding')
    report=dict(summary=summary,windows=windows,checks=checks,passed=all(checks.values()),release_ready=False,
        sources=sources,artifacts={p.name:sha(p) for p in out.iterdir()},scope=scope)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(summary))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True)
    review(**vars(p.parse_args()))
