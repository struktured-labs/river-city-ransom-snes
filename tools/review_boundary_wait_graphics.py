"""Publish every changed picture for boundary-wait3919 and retain failed text deadlines."""
import argparse
import html
import json
from pathlib import Path
import shutil
from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha,verify_capture


def review(before,after,audit,out):
    if out.exists():raise ValueError('Fresh output required')
    sources={str(Path(__file__)):sha(Path(__file__))};runs={};rows={};folders={}
    result=json.loads((audit/'report.json').read_text())
    for p,h in result['sources'].items():
        if sha(Path(p))!=h:raise ValueError('Changed text evidence')
    sources.update(result['sources']);sources[str(audit/'report.json')]=sha(audit/'report.json')
    for name,root in (('before',before),('after',after)):
        proof=bound_report(root/'publication-state.json')
        if not proof['observer_neutral']:raise ValueError('Non-neutral memory observation')
        sources.update(proof['sources']);sources[str(root/'publication-state.json')]=sha(root/'publication-state.json')
        normal=Path(proof['normal']);receipt,rows[name]=verify_capture(normal);folders[name]=normal
        runs[name]=dict(rom_sha256=receipt['rom_sha256'],frames=receipt['frames'])
    a,b=rows['before'],rows['after']
    if len(a)!=len(b):raise ValueError('Different route length')
    diff={k:[x['frame'] for x,y in zip(a,b) if x[k]!=y[k]] for k in
          ('probe_052b','input_requested','input_delivered','video_sha256')}
    diff['camera']=[x['frame'] for x,y in zip(a,b) if x['native']['logical_camera_x']!=y['native']['logical_camera_x']]
    words=[r for r in result['records'] if r['words'] or r['changed_source_addresses']]
    summary=dict(runs=runs,difference_counts={k:len(v) for k,v in diff.items()},text=words,
                 no_publication_regression=result['no_publication_regression'])
    out.mkdir()
    body='<!doctype html><meta charset="utf-8"><title>Boundary wait: graphics tradeoff</title><style>body{background:#101820;color:#eef;font:17px system-ui;max-width:1100px;margin:30px auto}a{color:cyan}pre{white-space:pre-wrap}.pair{display:flex;gap:12px}img{width:48%;image-rendering:pixelated}</style><h1>Boundary wait: better audio timing, two late text words</h1><p>3890 before /3919 after. Every full-route changed picture is retained. Memory observation preserves all primary frames/native PCM in each arm. Two text deadlines fail: this is not a release-ready result.</p><p><a href="../audio-boundary-wait80-audio-review-3922/">Exact-build native audio and packet intervals</a> · <a href="../audio-boundary-wait80-combat-review-3927/">Combat</a> · <a href="report.json">All raw differences</a> · <a href="../progress-3728/">Progress</a></p>'
    body+='<pre>'+html.escape(json.dumps(summary,indent=2))+'</pre>'
    for f in diff['video_sha256']:
        body+=f'<h2>Frame {f}</h2><div class="pair">'
        for name in ('before','after'):
            row=rows[name][f-1];p=folders[name]/row['frame_image']
            if sha(p)!=row['frame_image_sha256']:raise ValueError('Changed picture')
            dest=f'{name}-{f}.png';shutil.copyfile(p,out/dest);sources[str(p)]=sha(p)
            body+=f'<img loading="lazy" src="{dest}" alt="{name} frame{f}">'
        body+='</div>'
    (out/'index.html').write_text(body)
    for p in (Path('tools/audit_main_display_latency.py'),Path('tools/benchmark_report.py')):sources[str(p)]=sha(p)
    if any(sha(Path(p))!=h for p,h in sources.items()):raise ValueError('Changed source')
    report=dict(summary=summary,differences=diff,sources=sources,
        artifacts={p.name:sha(p) for p in out.iterdir()},release_ready=False,pop_free_verified=False)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(summary))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('before','after','audit','out'):p.add_argument('--'+k,type=Path,required=True)
    review(**vars(p.parse_args()))
