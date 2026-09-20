"""Retain all prefix pictures and actual CPU packet-transfer costs for local SPC polling."""
import argparse
import csv
import html
import json
from pathlib import Path
import shutil
from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha,verify_capture
from tools.capture_sprite_prefix import installed_prefix


def review(before,after,out):
    if out.exists():raise ValueError('Fresh output required')
    sources={str(Path(__file__)):sha(Path(__file__))};runs={};rows={}
    for name,root in (('before',before),('after',after)):
        proof=bound_report(root/'service-instructions.json')
        if not proof['observer_neutral'] or proof.get('last_phase')!='right_08' or (proof['first'],proof['last'])!=(2205,2207):
            raise ValueError('Wrong or non-neutral prefix trace')
        with installed_prefix('right_08'):receipt,rows[name]=verify_capture(root)
        sources.update(proof['sources'])
        for p in (root/'service-instructions.json',root/'timeline.json',root/'audio.wav'):sources[str(p)]=sha(p)
        active=None;calls=[]
        for r in csv.reader(Path(proof['trace']).open()):
            pc=int(r[4],16)
            if pc==0xc0d2bc:
                if active is not None:raise ValueError('Nested transfer')
                active=r
            if pc==0xc0d2f9:
                if active is None or active[9]!=r[9]:raise ValueError('Unmatched transfer')
                calls.append(dict(frame=int(active[0]),start_line=int(active[1]),start_cycle=int(active[2]),
                    end_frame=int(r[0]),end_line=int(r[1]),end_cycle=int(r[2]),clocks=int(r[3])-int(active[3])))
                active=None
        if active is not None or [c['frame'] for c in calls]!=[2205,2206,2207]:raise ValueError('Censored transfer coverage')
        runs[name]=dict(rom_sha256=receipt['rom_sha256'],calls=calls,
            mean_clocks=sum(c['clocks'] for c in calls)/len(calls),replay_seconds=proof['replay_seconds'])
    a,b=rows['before'],rows['after']
    if len(a)!=len(b):raise ValueError('Different prefix lengths')
    differences={k:[x['frame'] for x,y in zip(a,b) if x[k]!=y[k]] for k in
                 ('probe_052b','input_requested','input_delivered','video_sha256')}
    differences['camera']=[x['frame'] for x,y in zip(a,b) if x['native']['logical_camera_x']!=y['native']['logical_camera_x']]
    summary=dict(runs=runs,frames=len(a),difference_counts={k:len(v) for k,v in differences.items()})
    out.mkdir()
    body='<!doctype html><meta charset="utf-8"><title>SPC local poll</title><style>body{background:#101820;color:#eef;font:17px system-ui;max-width:1100px;margin:30px auto}a{color:cyan}pre{white-space:pre-wrap}.pair{display:flex;gap:10px}img{width:48%;image-rendering:pixelated}</style><h1>SPC local polling: measured transfer cost</h1><p>Same-core full prefix timeline/native PCM neutrality in each arm. Three actual sender calls; not a whole-game speed percentage. Two calls improve and one is slower. All changed prefix pictures retained. Native audio is copied untouched, not aligned or normalized. No release or pop-free verdict.</p>'
    for name,root in (('before',before),('after',after)):
        shutil.copyfile(root/'audio.wav',out/(name+'.wav'))
        body+=f'<h2>{name}</h2><audio controls preload="none" src="{name}.wav"></audio>'
    body+='<pre>'+html.escape(json.dumps(summary,indent=2))+'</pre><p><a href="report.json">Every difference and source binding</a> · <a href="../receiver-local-poll-audio-review-3942/">Full-route audio check</a></p>'
    for f in differences['video_sha256']:
        body+=f'<h2>Frame {f}</h2><div class="pair">'
        for name,root in (('before',before),('after',after)):
            row=rows[name][f-1];p=root/row['frame_image']
            if sha(p)!=row['frame_image_sha256']:raise ValueError('Changed picture')
            dest=f'{name}-{f}.png';shutil.copyfile(p,out/dest);sources[str(p)]=sha(p)
            body+=f'<img src="{dest}" alt="{name} frame{f}" loading="lazy">'
        body+='</div>'
    (out/'index.html').write_text(body)
    for p in (Path('tools/audit_main_display_latency.py'),Path('tools/benchmark_report.py'),Path('tools/capture_sprite_prefix.py')):sources[str(p)]=sha(p)
    if any(sha(Path(p))!=h for p,h in sources.items()):raise ValueError('Changed source')
    (out/'report.json').write_text(json.dumps(dict(summary=summary,differences=differences,sources=sources,
        artifacts={p.name:sha(p) for p in out.iterdir()},release_ready=False,pop_free_verified=False),indent=2)+'\n')
    print(json.dumps(summary))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('before','after','out'):p.add_argument('--'+k,type=Path,required=True)
    review(**vars(p.parse_args()))
