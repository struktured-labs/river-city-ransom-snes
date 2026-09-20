"""Retain the measured command stall and the unsuccessful whole-route timing tradeoff."""
import argparse
from collections import Counter
import csv
import html
import json
from pathlib import Path
import shutil
from tools.benchmark_report import sha, verify_capture

def bound(path):
    r=json.loads(path.read_text())
    for p,h in r['sources'].items():
        if sha(Path(p))!=h:raise ValueError('Changed binding: '+p)
    for p,h in r.get('artifacts',{}).items():
        if sha(path.parent/p)!=h:raise ValueError('Changed artifact: '+p)
    return r

def commands(rows):
    if any(int(b[0])<=int(a[0]) for a,b in zip(rows,rows[1:])):raise ValueError('Nonmonotonic SPC trace')
    result=[]
    for i,a in enumerate(rows):
        if a[7]!='215' or (i and rows[i-1][7]=='215'):continue
        if not i:raise ValueError('Left-censored command')
        j=i
        while j<len(rows) and rows[j][8]!='215':j+=1
        if j==len(rows):raise ValueError('Right-censored command')
        costs=Counter()
        for k in range(i,j):costs[rows[k][1]]+=int(rows[k+1][0])-int(rows[k][0])
        result.append(dict(first_tick=int(a[0]),ack_tick=int(rows[j][0]),spc_clocks=int(rows[j][0])-int(a[0]),
            first_pc=a[1],ack_pc=rows[j][1],clocks_by_pc=dict(costs),rows=rows[i:j+1]))
    if not result:raise ValueError('No complete commands')
    return result

def waits(path):
    rows=list(csv.reader(path.open()));result={}
    for f in range(8484,8488):
        selected=[r for r in rows if int(r[0])==f];costs=[]
        for i,r in enumerate(selected):
            if r[4].lower()!='c0d253':continue
            end=next((x for x in selected[i:] if x[4].lower()=='c0d261'),None)
            if end is None:raise ValueError('Censored CPU wait')
            costs.append(int(end[3])-int(r[3]))
        if len(costs)!=14:raise ValueError('Incomplete packet wait sequence')
        result[str(f)]=dict(ready=costs[0],command=costs[1],data=costs[2:])
    return result

def review(out):
    if out.exists():raise ValueError('Fresh report required')
    profile=Path('build/spc-opcode-observed-3993/spc-opcodes.json')
    info=bound(profile)
    if not info['observer_neutral']:raise ValueError('Unproven observer')
    bound(Path('build/spc-opcode-control-3992/spc-opcodes.json'))
    events=commands(list(csv.reader(Path(info['trace']).open())))
    captures=[Path('build/early-oam-live-half-full-3957'),Path('build/command-publish-priority-full-3998')]
    verified=[verify_capture(p) for p in captures]; a,b=[r[1] for r in verified]
    if len(a)!=len(b):raise ValueError('Changed route length')
    changes={k:[x['frame'] for x,y in zip(a,b) if x[k]!=y[k]] for k in
        ('video_sha256','game_ram_hex','nmi_counter','input_requested','input_delivered','fault')}
    changes.update({k:[x['frame'] for x,y in zip(a,b) if x['native'][k]!=y['native'][k]] for k in
        ('logical_camera_x','game_nmi_ticks_010b')})
    paths=[Path(__file__),Path('tests/test_command_priority_review.py'),profile,Path(info['trace'])]
    audio=[];cpu=[];fixtures=[]
    for p in ('build/early-oam-live-half-audio-review-3962/report.json','build/command-publish-priority-audio-review-4000/report.json'):
        path=Path(p);audio.append(bound(path)['summary']);paths.append(path)
    for p in ('build/early-oam-live-half-worst-audio-3988','build/command-publish-priority-cpu-4001'):
        root=Path(p);proof=bound(root/'service-instructions.json');trace=Path(proof['trace'])
        cpu.append(waits(trace));paths.extend((root/'service-instructions.json',trace))
    for p in ('build/command-priority-spc-3995/report.json','build/command-publish-priority-spc-3997/report.json'):
        path=Path(p);fixtures.append(bound(path));paths.append(path)
    if fixtures[0]['passed'] or not fixtures[1]['passed']:raise ValueError('Unexpected experiment verdict')
    paths.extend(p/'capture.json' for p in captures)
    out.mkdir();cards=[]
    for frame in changes['video_sha256']:
        images=[]
        for side,root,rows in zip(('before','after'),captures,(a,b)):
            source=root/rows[frame-1]['frame_image'];name=f'{side}-{frame}.png'
            shutil.copyfile(source,out/name);images.append(f'<figure><img src="{name}"><figcaption>{side}</figcaption></figure>')
        cards.append(f'<section><h3>Frame {frame}: {html.escape(a[frame-1]["phase"])}</h3><div class="pair">'+''.join(images)+'</div></section>')
    summary=dict(command_spc_clocks=[r['spc_clocks'] for r in events],cpu_waits=dict(before=cpu[0],after=cpu[1]),
        audio=dict(before=audio[0],after=audio[1]),changed_field_counts={k:len(v) for k,v in changes.items()},
        rejected_skip_all_idle=True,timer_preserving_trial_passes_spc=True,whole_route_worst_gap_improved=False,
        release_ready=False,deployed=False)
    body='''<!doctype html><meta charset="utf-8"><title>Command wait: local gain, route tradeoff</title>
<style>body{background:#101820;color:#eef;font:17px system-ui;max-width:1100px;margin:30px auto}a{color:cyan}pre{white-space:pre-wrap}.pair{display:flex;gap:16px}figure{margin:0}img{width:512px;image-rendering:pixelated;max-width:100%}</style>
<h1>Command wait isolated; trial not promoted</h1>
<p>3955 read-only SPC observation preserved all9,090 frames and native PCM. The worst observed command waits772 SPC clocks while timer/sweep work and two pulse publications execute before acknowledgement.</p>
<p>3994 bypassed all idle work and failed continuous timer deadlines.3996 preserves timer polling and skips old-state publication only when D7 is pending. Its executed timer and ownership checks pass; timer-drop and legacy-writer controls fail.</p>
<p>Frame8486 command wait improves16,176→4,982 CPU master clocks. But the full-route worst packet gap worsens20.858→21.037ms (now8531→8532). The old8485→8486 gap improves to20.386ms. Local wait savings do not prove pop-free sound or original-NES speed. No hardware or release change.</p>
<p><a href="../command-publish-priority-audio-review-4000/">Complete native trial audio and timing</a> · <a href="../early-oam-live-half-audio-review-3962/">Parent native audio</a> · <a href="https://github.com/struktured-labs/river-city-ransom-snes/issues/6">Audio issue6</a> · <a href="report.json">All differences, raw command rows, bindings</a></p>
<h2>Every changed picture (parent3955 / trial3996)</h2>'''+''.join(cards)+'<h2>Measurements</h2><pre>'+html.escape(json.dumps(summary,indent=2))+'</pre>'
    (out/'index.html').write_text(body)
    report=dict(summary=summary,commands=events,changed_frames=changes,sources={str(p):sha(p) for p in paths},
        artifacts={p.name:sha(p) for p in out.iterdir()},scope=__doc__)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(summary['changed_field_counts']))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True)
    review(**vars(p.parse_args()))
