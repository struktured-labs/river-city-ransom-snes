"""Compare guarded post-preparation recovery with both retained scheduling controls."""
import argparse
import csv
import html
import json
from pathlib import Path
import shutil
from tools.benchmark_report import sha, verify_capture
from tools.review_command_priority import bound
from tools.analyze_audio_bus import analyze
from tools.analyze_spc_receive import compare

ARMS = [
    ('3955','early-oam-live-half-full-3957','early-oam-live-half-audio-3961','early-oam-live-half-audio-review-3962'),
    ('4033','audio-regular-irq-full-4035','audio-regular-irq-observed-4036','audio-regular-irq-audio-review-4037'),
    ('4041','audio-pre-retained-full-4042','audio-pre-retained-observed-4043','audio-pre-retained-audio-review-4044'),
    ('4046','audio-dual-boundary-full-4047','audio-dual-boundary-observed-4048','audio-dual-boundary-audio-review-4049')]


def timing_improves(parent, trial):
    return (trial['minimum_ms'] >= parent['minimum_ms'] and
            trial['maximum_ms'] <= parent['maximum_ms'] and
            (trial['minimum_ms'] > parent['minimum_ms'] or trial['maximum_ms'] < parent['maximum_ms']))


def review(out):
    if out.exists():raise ValueError('Fresh output required')
    sources={str(p):sha(p) for p in (Path(__file__),Path('tests/test_audio_pre_retained_review.py'),
        Path('tools/analyze_audio_bus.py'),Path('tools/analyze_spc_receive.py'),Path('tools/review_command_priority.py'))}
    rows={};audio={};packets={};transport={};changes={};negative=False
    for tag,normal,observed,report in ARMS:
        root=Path('build')/normal; obs=Path('build')/observed
        receipt,rows[tag]=verify_capture(root)
        for proof in (obs/'startup-game.json',Path('build')/report/'report.json'):
            data=bound(proof);sources[str(proof)]=sha(proof)
        audio[tag]=data['summary']
        sources[str(root/'capture.json')]=sha(root/'capture.json')
        obs_receipt,_=verify_capture(obs)
        traces=obs_receipt['dsp_latency_observer']['traces']
        values=[]
        for key in ('RCR_AUDIO_BUS_TRACE','RCR_SPC_RECEIVE_TRACE'):
            p=Path(traces[key]['path'])
            if sha(p)!=traces[key]['sha256']:raise ValueError('Changed trace')
            sources[str(p)]=sha(p);values.append(list(csv.reader(p.open())))
        bus,rx=values
        source=analyze(bus,length_gate=True)
        transfer=compare(bus,rx,paired=True,receiver_pcs=[0x32e5,0x32f1])
        if source['mismatches'] or source['unflushed_cpu_writes'] or not transfer['passed']:
            raise ValueError('Incomplete/changed sound transfer')
        packets[tag]=source['packets']
        transport[tag]={k:transfer[k] for k in ('packets','bytes_compared','mismatch_count','passed')}
        if tag=='4046':
            bad=[r.copy() for r in rx];bad[0][1]=str(int(bad[0][1])^1)
            negative=not compare(bus,bad,paired=True,receiver_pcs=[0x32e5,0x32f1])['passed']
        if tag!='3955':
            a,b=rows['3955'],rows[tag]
            if len(a)!=len(b):raise ValueError('Changed route coverage')
            changes[tag]={k:[x['frame'] for x,y in zip(a,b) if x[k]!=y[k]] for k in
                ('video_sha256','game_ram_hex','nmi_counter','input_requested','input_delivered','fault')}
            changes[tag].update({k:[x['frame'] for x,y in zip(a,b) if x['native'][k]!=y['native'][k]] for k in
                ('logical_camera_x','game_nmi_ticks_010b')})
    if not negative:raise ValueError('Corrupted-byte control escaped')
    payloads={}
    for tag in ('4033','4041','4046'):
        if len(packets[tag])!=len(packets['3955']):raise ValueError('Different packet counts')
        payloads[tag]=[dict(packet=i+1,before=x,after=y) for i,(x,y) in enumerate(zip(packets['3955'],packets[tag])) if x['bytes']!=y['bytes']]
    cpu={}
    for tag,root in [('4033','audio-regular-irq-late-cpu-4040'),('4041','audio-pre-retained-cpu-4045')]:
        p=Path('build')/root/'service-instructions.json';proof=bound(p)
        if not proof['observer_neutral']:raise ValueError('Unproven CPU observer')
        verify_capture(p.parent);trace=Path(proof['trace'])
        cpu[tag]=[r for r in csv.reader(trace.open()) if r[0]=='2120' and int(r[4],16)&65535 in
            (0x325c,0x325f,0x3268,0x326b,0x3282,0x7885,0xfa54,0xfa64,0x7f40)]
        for x in (p,trace):sources[str(x)]=sha(x)
    summary=dict(audio=audio,transport=transport,payload_change_counts={k:len(v) for k,v in payloads.items()},
        changes={k:{f:len(v) for f,v in arm.items()} for k,arm in changes.items()},
        timing_improves_baseline={k:timing_improves(audio['3955']['packet_cadence'],audio[k]['packet_cadence']) for k in ('4033','4041','4046')},
        corrupted_receive_control_rejected=negative,release_ready=False,pop_free_verified=False)
    out.mkdir();cards=[]
    frames=sorted(set(f for arm in changes.values() for f in arm['video_sha256']))
    for f in frames:
        images=[]
        for tag,normal,_,_ in ARMS:
            name=f'{tag}-{f}.png';shutil.copyfile(Path('build')/normal/rows[tag][f-1]['frame_image'],out/name)
            images.append(f'<figure><img loading="lazy" src="{name}"><figcaption>{tag}</figcaption></figure>')
        cards.append(f'<h3>Frame {f}</h3><div class="grid">'+''.join(images)+'</div>')
    table=''.join(f'<tr><td>{tag}</td><td>{audio[tag]["packet_cadence"]["minimum_ms"]:.3f}</td><td>{audio[tag]["packet_cadence"]["maximum_ms"]:.3f}</td><td><a href="../{report}/">Native audio</a></td></tr>' for tag,_,_,report in ARMS)
    body='''<!doctype html><meta charset="utf-8"><title>Pre-retained sound recovery</title>
<style>body{background:#101820;color:#eef;font:17px system-ui;max-width:1100px;margin:30px auto}a{color:cyan}pre{white-space:pre-wrap}.grid{display:grid;grid-template-columns:1fr 1fr}img{width:480px;image-rendering:pixelated}figure{margin:8px}td,th{padding:8px}</style>
<h1>Sound recovery before retained game-NMI work</h1>
<p>4041 adds guarded recovery after camera preparation to4033 (early service disabled).4046 restores the baseline early service as well. Original graphics and SPC bytes remain unchanged. No hardware or release promotion.</p>
<p>In neutral CPU frame2120,4041 starts the original sound driver at line98 instead of156. The wrapper returns to the original branch with stack position507 unchanged. This is not a complete CPU-context or all-scene timing proof.</p>
<table><tr><th>Build</th><th>Minimum stable gap ms</th><th>Maximum ms</th><th>Evidence</th></tr>'''+table+'</table><p>Every arm retains7,342 stable and1,298 excluded intervals. No clipping is not a pop-free certificate. All sound payload differences and picture differences are retained.</p><p><a href="report.json">Complete differences and bindings</a> · <a href="https://github.com/struktured-labs/river-city-ransom-snes/issues/6">Audio issue</a></p><details><summary>Full measurements</summary><pre>'+html.escape(json.dumps(summary,indent=2))+'</pre></details><h2>Every changed picture, baseline3955 /4033 /4041 /4046</h2>'+''.join(cards)
    (out/'index.html').write_text(body)
    if any(sha(Path(p))!=h for p,h in sources.items()):raise ValueError('Changed source')
    (out/'report.json').write_text(json.dumps(dict(summary=summary,cpu_events=cpu,changed_frames=changes,
        packet_changes=payloads,sources=sources,artifacts={p.name:sha(p) for p in out.iterdir()},scope=__doc__),indent=2)+'\n')
    print(json.dumps({k:summary[k] for k in ('payload_change_counts','timing_improves_baseline','changes')}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True)
    review(**vars(p.parse_args()))
