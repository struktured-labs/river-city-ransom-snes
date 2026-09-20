"""Auditable full-route pictures and sampled text deadlines for a row-search trial."""
import argparse
import html
import json
from pathlib import Path
import shutil
import wave
from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha, verify_capture


def review(before,after,out):
    if out.exists():raise ValueError('Fresh output required')
    sources={}; runs={}; timelines={}; folders={}
    for name,folder in (('before',before),('after',after)):
        proof=bound_report(folder/'publication-state.json')
        if not proof['observer_neutral']:raise ValueError('Need neutral memory observation')
        normal=Path(proof['normal'])
        receipt,rows=verify_capture(normal)
        sources.update(proof['sources'])
        sources[str(folder/'publication-state.json')]=sha(folder/'publication-state.json')
        cases=[]
        for frame,column in ((5989,11),(5991,12)):
            raw=Path(proof['samples'][str(frame)]['path']).read_bytes()
            source=raw[0x12000+25*32+column]
            stage=raw[0x3000+25*64+column*2:0x3000+25*64+column*2+2]
            actual=raw[0x24000+25*64+column*2:0x24000+25*64+column*2+2]
            cases.append(dict(frame=frame,row=25,column=column,source=source,
                prepared=stage.hex(),actual=actual.hex(),matches_own_prepared=stage==actual))
        runs[name]=dict(rom_sha256=receipt['rom_sha256'],frames=len(rows),cases=cases,
            observer_neutral=True,state_capture_seconds=proof['elapsed_seconds'])
        timelines[name]=rows;folders[name]=normal
    a,b=timelines['before'],timelines['after']
    if len(a)!=len(b):raise ValueError('Different route lengths')
    differences={k:[x['frame'] for x,y in zip(a,b) if x[k]!=y[k]]
        for k in ('probe_052b','input_requested','input_delivered','video_sha256')}
    differences['camera']=[x['frame'] for x,y in zip(a,b)
        if x['native']['logical_camera_x']!=y['native']['logical_camera_x']]
    out.mkdir()
    frames=sorted(set((5989,5991))|set(differences['video_sha256']))
    for name,normal in folders.items():
        for frame in frames:
            path=normal/timelines[name][frame-1]['frame_image']
            shutil.copyfile(path,out/f'{name}-{frame}.png')
            sources[str(path)]=sha(path)
        # Identical unaligned96–102s native clip, includes the dialogue examples.
        with wave.open(str(normal/'audio.wav')) as stream:
            if (stream.getframerate(),stream.getnchannels(),stream.getsampwidth())!=(32040,2,2):
                raise ValueError('Unexpected native audio')
            stream.setpos(96*32040);payload=stream.readframes(6*32040)
            if len(payload)!=6*32040*4:raise ValueError('Truncated clip')
        with wave.open(str(out/(name+'.wav')),'wb') as stream:
            stream.setframerate(32040);stream.setnchannels(2);stream.setsampwidth(2);stream.writeframes(payload)
    summary=dict(runs=runs,difference_counts={k:len(v) for k,v in differences.items()})
    body=('<!doctype html><meta charset="utf-8"><title>Row-search trial</title>'
        '<style>body{background:#101820;color:#eef;font:17px system-ui;max-width:1100px;margin:30px auto}'
        'a{color:cyan}pre{white-space:pre-wrap}.pair{display:flex;gap:12px}img{width:48%;image-rendering:pixelated}</style>'
        '<h1>Row-search trial: exact pictures and remaining tradeoffs</h1>'
        '<p>Every full-route picture difference is retained. Memory observations are same-core '
        'neutral over the full route. These two deadline examples are not full-game qualification. '
        'Native clips use the same96–102s sample range, with no filtering, gain or alignment. '
        'No release or pop-free claim.</p>')
    for name in runs:body+=f'<h2>{name}</h2><audio controls preload="none" src="{name}.wav"></audio>'
    body+='<pre>'+html.escape(json.dumps(summary,indent=2))+'</pre>'
    body+='<p><a href="report.json">Full differences and source bindings</a> · <a href="../progress-3728/">Progress</a></p>'
    for frame in frames:
        body+=f'<h2>Frame {frame}</h2><div class="pair">'
        for name in runs:body+=f'<img loading="lazy" src="{name}-{frame}.png" alt="{name} frame{frame}">'
        body+='</div>'
    (out/'index.html').write_text(body)
    for p in (Path(__file__),Path('tools/audit_main_display_latency.py'),Path('tools/benchmark_report.py')):
        sources[str(p)]=sha(p)
    if any(sha(Path(p))!=h for p,h in sources.items()):raise ValueError('Changed source')
    report=dict(summary=summary,differences=differences,sources=sources,
        artifacts={p.name:sha(p) for p in out.iterdir()},release_ready=False,pop_free_verified=False)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(summary))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('before','after','out'):p.add_argument('--'+k,type=Path,required=True)
    review(**vars(p.parse_args()))
