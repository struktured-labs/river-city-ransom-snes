"""Compare exact phase48 trial against3890, without dropping camera or picture differences."""
import argparse
import csv
import html
import json
from pathlib import Path
import shutil
import wave
from tools.audit_main_display_latency import bound_report
from tools.audit_sound_service_phases import MS_PER_CLOCK
from tools.benchmark_report import sha, verify_capture


def review(before, after, out):
    if out.exists(): raise ValueError('Fresh output required')
    sources={str(Path(__file__)):sha(Path(__file__))}
    runs={}; timelines={}; artifacts={}
    for name, root in (('before',before),('after',after)):
        proof=bound_report(root/'service-instructions.json')
        if not proof['observer_neutral'] or (proof['first'],proof['last'])!=(8530,8533):
            raise ValueError('Wrong trace window or non-neutral observer')
        receipt,rows=verify_capture(root)
        sources.update(proof['sources'])
        for p in (root/'service-instructions.json',root/'timeline.json',root/'audio.wav'):
            sources[str(p)]=sha(p)
        timelines[name]=rows
        entries=[];returns=[]
        for r in csv.reader(Path(proof['trace']).open()):
            pc=int(r[4],16)
            if 0xc1<=pc>>16<=0xc8 and pc&65535 in (0xfa54,0xfa64):
                item=dict(frame=int(r[0]),line=int(r[1]),cycle=int(r[2]),clock=int(r[3]),stack=int(r[9]))
                (entries if pc&65535==0xfa54 else returns).append(item)
        if ([r['frame'] for r in entries]!=list(range(8530,8534)) or
            [r['frame'] for r in returns]!=list(range(8530,8534)) or
            any(a['clock']>=b['clock'] or a['stack']!=b['stack'] for a,b in zip(entries,returns))):
            raise ValueError('Missing or unmatched sound calls')
        runs[name]=dict(rom_sha256=receipt['rom_sha256'],entries=entries,returns=returns,
            return_gaps_ms=[(b['clock']-a['clock'])*MS_PER_CLOCK for a,b in zip(returns,returns[1:])],
            replay_seconds=proof['replay_seconds'])
    a,b=timelines['before'],timelines['after']
    if len(a)!=len(b): raise ValueError('Different route lengths')
    differences={k:[x['frame'] for x,y in zip(a,b) if x[k]!=y[k]] for k in
                 ('probe_052b','input_requested','input_delivered','video_sha256')}
    differences['logical_camera']=[dict(frame=x['frame'],before=x['native']['logical_camera_x'],
        after=y['native']['logical_camera_x']) for x,y in zip(a,b)
        if x['native']['logical_camera_x']!=y['native']['logical_camera_x']]
    out.mkdir()
    body='<!doctype html><meta charset="utf-8"><title>Audio phase48 tradeoff</title><style>body{background:#101820;color:#eef;font:17px system-ui;max-width:1100px;margin:30px auto}a{color:cyan}pre{white-space:pre-wrap}.pair{display:flex;gap:10px}img{width:48%;image-rendering:pixelated}</style><h1>Audio phase48: targeted improvement, full-route tradeoffs</h1><p>Same-core full primary timeline/native PCM observer neutrality in each arm. Four traced CPU frames. Native140–143s clips, no alignment, gain or filtering. Every changed route picture and camera sample retained. Not a release, original-speed or pop-free verdict.</p>'
    for name,root in (('before',before),('after',after)):
        with wave.open(str(root/'audio.wav')) as w:
            if (w.getframerate(),w.getnchannels(),w.getsampwidth())!=(32040,2,2):
                raise ValueError('Wrong PCM format')
            w.setpos(140*32040);data=w.readframes(3*32040)
            if len(data)!=3*32040*4: raise ValueError('Incomplete PCM')
        with wave.open(str(out/(name+'.wav')),'wb') as w:
            w.setnchannels(2);w.setsampwidth(2);w.setframerate(32040);w.writeframes(data)
        body+=f'<h2>{name}</h2><audio controls preload="none" src="{name}.wav"></audio>'
    summary=dict(runs=runs,difference_counts={k:len(v) for k,v in differences.items()})
    body+='<pre>'+html.escape(json.dumps(summary,indent=2))+'</pre><h2>Every changed picture</h2>'
    for f in differences['video_sha256']:
        body+=f'<h3>Frame {f}</h3><div class="pair">'
        for name,root in (('before',before),('after',after)):
            row=timelines[name][f-1];p=root/row['frame_image']
            if sha(p)!=row['frame_image_sha256']:raise ValueError('Changed picture')
            dest=f'{name}-{f}.png';shutil.copyfile(p,out/dest);sources[str(p)]=sha(p)
            body+=f'<img loading="lazy" src="{dest}" alt="{name} frame{f}">'
        body+='</div>'
    body+='<p><a href="report.json">Every difference and binding</a> · <a href="../alias-audio48-audio-review-3916/">Whole-route audio verdict</a> · <a href="../progress-3728/">Progress</a></p>'
    (out/'index.html').write_text(body)
    for p in (Path('tools/audit_main_display_latency.py'),Path('tools/audit_sound_service_phases.py'),Path('tools/benchmark_report.py')):
        sources[str(p)]=sha(p)
    if any(sha(Path(p))!=h for p,h in sources.items()):raise ValueError('Changed sources')
    report=dict(summary=summary,differences=differences,sources=sources,
        artifacts={p.name:sha(p) for p in out.iterdir()},release_ready=False,pop_free_verified=False)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(summary))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('before','after','out'):p.add_argument('--'+k,type=Path,required=True)
    review(**vars(p.parse_args()))
