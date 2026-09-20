"""CPU/SPC attribution and complete route tradeoffs for pending-token priority."""
import argparse
import csv
import html
import json
from pathlib import Path
import shutil
from tools.review_command_priority import bound
from tools.benchmark_report import sha,verify_capture

def cpu_windows(rows, first=8530, last=8533):
    result=[]
    for f in range(first,last+1):
        records=[r for r in rows if int(r[0])==f]
        def pair(entry,exit,mask=0xffffff):
            starts=[i for i,r in enumerate(records) if int(r[4],16)&mask==entry]
            if len(starts)!=1:raise ValueError('Missing or duplicate service entry')
            i=starts[0];ends=[r for r in records[i+1:] if int(r[4],16)&mask==exit]
            if len(ends)!=1:raise ValueError('Missing or duplicate service exit')
            a,b=records[i],ends[0]
            if int(b[3])<=int(a[3]):raise ValueError('Nonpositive service span')
            return dict(start_clock=int(a[3]),end_clock=int(b[3]),clocks=int(b[3])-int(a[3]),
                start_line=int(a[1]),start_cycle=int(a[2]),end_line=int(b[1]),end_cycle=int(b[2]))
        driver=pair(0xfa54,0xfa64,0xffff);sender=pair(0xc0d2bc,0xc0d2f9)
        active=None;waits=[]
        for r in records:
            if r[4]=='c0d253':
                if active:raise ValueError('Nested wait')
                active=r
            if r[4]=='c0d261':
                if not active:raise ValueError('Unmatched wait exit')
                waits.append(int(r[3])-int(active[3]));active=None
        if active or len(waits)!=14:raise ValueError('Censored wait coverage')
        result.append(dict(frame=f,driver=driver,sender=sender,ready=waits[0],command=waits[1],data=waits[2:]))
    return result

def token_events(rows):
    events=[]
    if any(int(y[0])<=int(x[0]) for x,y in zip(rows,rows[1:])):raise ValueError('Nonmonotonic SPC trace')
    for i,r in enumerate(rows):
        if not i or r[7]!='22' or rows[i-1][7]=='22':continue
        end=next((j for j in range(i,len(rows)) if rows[j][8]=='22'),None)
        if end is None:raise ValueError('Censored last token')
        events.append(dict(first_tick=int(r[0]),ack_tick=int(rows[end][0]),clocks=int(rows[end][0])-int(r[0]),rows=rows[i:end+1]))
    if not events:raise ValueError('No final-token events')
    return events

def review(out):
    if out.exists():raise ValueError('Fresh report required')
    sources={str(p):sha(p) for p in (Path(__file__),Path('tools/review_command_priority.py'),Path('tests/test_token_priority_review.py'))}
    profiles={}
    for tag,p in [('3955','build/command-gap-parent-cpu-4003'),('3996','build/command-gap-trial-cpu-4004'),('4007','build/receiver-token-priority-cpu-4012')]:
        root=Path(p);proof=bound(root/'service-instructions.json')
        if not proof['observer_neutral']:raise ValueError('Non-neutral CPU trace')
        trace=Path(proof['trace']);profiles[tag]=cpu_windows(list(csv.reader(trace.open())))
        for path in (root/'service-instructions.json',trace):sources[str(path)]=sha(path)
    proofpath=Path('build/moved-gap-opcode-observed-4006/spc-opcodes.json');proof=bound(proofpath)
    if not proof['observer_neutral']:raise ValueError('Non-neutral SPC trace')
    bound(Path('build/moved-gap-opcode-control-4005/spc-opcodes.json'))
    events=token_events(list(csv.reader(Path(proof['trace']).open())))
    for path in (proofpath,Path(proof['trace'])):sources[str(path)]=sha(path)
    audio={}
    for tag,p in [('3955','build/early-oam-live-half-audio-review-3962'),('3996','build/command-publish-priority-audio-review-4000'),('4007','build/receiver-token-priority-audio-review-4011')]:
        path=Path(p)/'report.json';audio[tag]=bound(path)['summary'];sources[str(path)]=sha(path)
    fixture=Path('build/receiver-token-priority-spc-4008/report.json')
    if not bound(fixture)['passed']:raise ValueError('SPC fixture failed')
    sources[str(fixture)]=sha(fixture)
    roots=[Path(p) for p in ('build/early-oam-live-half-full-3957','build/command-publish-priority-full-3998','build/receiver-token-priority-full-4009')]
    rows=[verify_capture(root)[1] for root in roots]
    if len({len(r) for r in rows})!=1:raise ValueError('Different frame coverage')
    differences={}
    for tag,baseline in zip(('3955','3996'),rows[:2]):
        differences[tag]={k:[a['frame'] for a,b in zip(baseline,rows[2]) if a[k]!=b[k]] for k in ('video_sha256','game_ram_hex','nmi_counter','input_requested','input_delivered','fault')}
        differences[tag].update({k:[a['frame'] for a,b in zip(baseline,rows[2]) if a['native'][k]!=b['native'][k]] for k in ('logical_camera_x','game_nmi_ticks_010b')})
    for root in roots:sources[str(root/'capture.json')]=sha(root/'capture.json')
    summary=dict(cpu=profiles,audio=audio,difference_counts={k:{n:len(v) for n,v in arm.items()} for k,arm in differences.items()},
        spc_final_token_clocks=[e['clocks'] for e in events],release_ready=False,deployed=False)
    out.mkdir();cards=[]
    changed=sorted(set(differences['3955']['video_sha256'])|set(differences['3996']['video_sha256']))
    for f in changed:
        pics=[]
        for tag,root,records in zip(('3955','3996','4007'),roots,rows):
            source=root/records[f-1]['frame_image'];name=f'{tag}-{f}.png';shutil.copyfile(source,out/name)
            pics.append(f'<figure><img loading="lazy" src="{name}"><figcaption>{tag}</figcaption></figure>')
        cards.append(f'<h3>Frame{f}: {html.escape(rows[0][f-1]["phase"])}</h3><div class="pictures">'+''.join(pics)+'</div>')
    body='''<!doctype html><meta charset="utf-8"><title>Pending token priority</title>
<style>body{background:#101820;color:#eef;font:17px system-ui;max-width:1200px;margin:30px auto}a{color:cyan}pre{white-space:pre-wrap}.pictures{display:flex;gap:10px}figure{margin:0;width:33%}img{width:100%;image-rendering:pixelated}</style>
<h1>Receiver4007: service a waiting data byte before timer work</h1>
<p>Exact3996 trace shows the final token already pending at3530, before a consuming timer read. Timer/sweep processing delays its acknowledgement379 SPC clocks; the neighboring final token takes35. CPU profiles also retain original-driver variation and early-camera versus normal-interrupt service phases.</p>
<p>The16-byte receiver variant checks the token first; unmatched waits and packet completion still process timers using active controls. Both modes/four sender delays pass actual SPC continuous-clock checks; timer-drop and legacy-volume-write mutants fail. No sound samples, graphics or CPU scheduling changed. Full-game timing and pictures can still change as a consequence.</p>
<p>This is an experiment, not a release or a pop-free/original-NES-speed claim. All primary differences, excluded audio intervals and native audio remain available.</p>
<p><a href="../receiver-token-priority-audio-review-4011/">4007 native audio and every interval</a> · <a href="../command-publish-priority-audio-review-4000/">3996 native audio</a> · <a href="../early-oam-live-half-audio-review-3962/">3955 native audio</a> · <a href="https://github.com/struktured-labs/river-city-ransom-snes/issues/6">Issue6</a> · <a href="report.json">Raw evidence and bindings</a></p>
<h2>Measured costs and complete-route audio</h2><pre>'''+html.escape(json.dumps(summary,indent=2))+'</pre><h2>Every changed picture:3955 /3996 /4007</h2>'+''.join(cards)
    (out/'index.html').write_text(body)
    if any(sha(Path(p))!=h for p,h in sources.items()):raise ValueError('Changed source')
    report=dict(summary=summary,differences=differences,token_events=events,sources=sources,
        artifacts={p.name:sha(p) for p in out.iterdir()},scope=__doc__)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(summary['difference_counts']))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True)
    review(**vars(p.parse_args()))
