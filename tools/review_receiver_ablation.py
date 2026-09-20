"""Receiver ablation: preserve all sound payloads and retain the graphics/timing failure."""
import argparse
import csv
import html
import json
from pathlib import Path
import shutil
from tools.analyze_audio_bus import analyze
from tools.review_command_priority import bound
from tools.benchmark_report import sha,verify_capture

def identical_payloads(a,b):
    return bool(a) and len(a)==len(b) and all(x['bytes']==y['bytes'] for x,y in zip(a,b))

def review(out):
    if out.exists():raise ValueError('Fresh output required')
    sources={str(p):sha(p) for p in (Path(__file__),Path('tests/test_receiver_ablation.py'),Path('tools/analyze_audio_bus.py'),Path('tools/review_command_priority.py'))}
    metrics={};text={}
    for tag,p in [('3955','build/early-oam-live-half-audio-review-3962'),('3996','build/command-publish-priority-audio-review-4000'),('4007','build/receiver-token-priority-audio-review-4011'),('4025','build/receiver-token-only-audio-review-4029')]:
        path=Path(p)/'report.json';metrics[tag]=bound(path)['summary'];sources[str(path)]=sha(path)
    for tag,p in [('4007','build/receiver-token-priority-text-review-4023'),('4025','build/receiver-token-only-text-review-4031')]:
        path=Path(p)/'report.json';text[tag]=bound(path);sources[str(path)]=sha(path)
    payloads=[]
    for p in ('build/early-oam-live-half-audio-3961-bus.csv','build/receiver-token-only-audio-4028-bus.csv'):
        path=Path(p);sources[str(path)]=sha(path);data=analyze(list(csv.reader(path.open())),length_gate=True)
        if data['mismatches'] or data['unflushed_cpu_writes']:raise ValueError('Bad source stream')
        payloads.append(data['packets'])
    if not identical_payloads(*payloads):raise ValueError('Ablation payloads differ')
    bad=[dict(x) for x in payloads[1]];bad[0]['bytes']='00'+bad[0]['bytes'][2:]
    if bad[0]['bytes']==payloads[1][0]['bytes']:bad[0]['bytes']='01'+bad[0]['bytes'][2:]
    if identical_payloads(payloads[0],bad) or identical_payloads(payloads[0],payloads[1][:-1]):raise ValueError('Payload mutant escaped')
    roots=[Path(p) for p in ('build/early-oam-live-half-full-3957','build/receiver-token-priority-full-4009','build/receiver-token-only-full-4027')]
    rows=[verify_capture(p)[1] for p in roots]
    if len({len(r) for r in rows})!=1:raise ValueError('Unequal route coverage')
    changes={}
    for tag,b in zip(('4007','4025'),rows[1:]):
        changes[tag]={k:[x['frame'] for x,y in zip(rows[0],b) if x[k]!=y[k]] for k in ('video_sha256','game_ram_hex','nmi_counter','input_requested','input_delivered','fault')}
        changes[tag].update({k:[x['frame'] for x,y in zip(rows[0],b) if x['native'][k]!=y['native'][k]] for k in ('logical_camera_x','game_nmi_ticks_010b')})
    for p in roots:sources[str(p/'capture.json')]=sha(p/'capture.json')
    out.mkdir();table=[]
    for tag,m in metrics.items():
        c=m['packet_cadence'];table.append(f'<tr><td>{tag}</td><td>{c["minimum_ms"]:.3f}</td><td>{c["maximum_ms"]:.3f}</td><td>{m["audio"]["restarts"]}</td></tr>')
    changed=sorted(set(changes['4007']['video_sha256'])|set(changes['4025']['video_sha256']))
    cards=[]
    for f in changed:
        card=f'<h3 id="frame-{f}">Frame {f}: {html.escape(rows[0][f-1]["phase"])}</h3><div class="pictures">'
        for tag,root,records in zip(('3955','4007','4025'),roots,rows):
            source=root/records[f-1]['frame_image'];name=f'{tag}-{f}.png';shutil.copyfile(source,out/name)
            card+=f'<figure><img src="{name}" loading="lazy"><figcaption>{tag}</figcaption></figure>'
        cards.append(card+'</div>')
    body='''<!doctype html><meta charset="utf-8"><title>Receiver ablation</title>
<style>body{background:#101820;color:#eef;font:17px system-ui;max-width:1200px;margin:30px auto}a{color:cyan}td,th{padding:8px;border-bottom:1px solid #456}pre{white-space:pre-wrap}.pictures{display:flex;gap:10px}figure{margin:0;width:33%}img{width:100%;image-rendering:pixelated}</style>
<h1>Same sound payloads; graphics and timing still block promotion</h1>
<p>4025 removes command-publication priority from4007, keeping only the data-token-first receiver. All8,641 ordered23-byte payloads now exactly match3955; dropped or corrupted packet controls fail. The current engine's continuous timer and volume-ownership tests pass. This does not make native PCM identical or establish pop-free sound.</p>
<table><tr><th>Candidate</th><th>Minimum gap ms</th><th>Maximum gap ms</th><th>Pulse restarts</th></tr>'''+''.join(table)+'''</table>
<p>4007 and4025 both fail the same graphics check: frame5989,row25,column11 is prepared asEB08, but only3955 has published it. Three source-text frames also differ (5980,5987,5988); eight compared words arrive earlier. No failed word or changed source is waived. <a href="#frame-5989">Late-tile pictures</a>.</p>
<p>All230 original sound requests in4007 match3955 by ID/order, with four one-frame shifts retained in the <a href="../sound-request-review-4024/">request audit</a>. That explains why request loss cannot be inferred from changed restart totals. It does not fully explain every sound-state difference.</p>
<p>No default ROM, hardware or release changes.3955 remains the graphics baseline; neither receiver variant earns promotion from these results. Further small transfer-priority changes are not justified by the route result alone.</p>
<p><a href="../receiver-token-only-audio-review-4029/">4025 native audio / every interval</a> · <a href="../receiver-token-priority-audio-review-4011/">4007 native audio</a> · <a href="../early-oam-live-half-audio-review-3962/">3955 native audio</a> · <a href="report.json">All differences, source stages and bindings</a> · <a href="https://github.com/struktured-labs/river-city-ransom-snes/issues/6">Audio issue6</a></p><h2>Every changed picture:3955 /4007 /4025</h2>'''+''.join(cards)
    (out/'index.html').write_text(body)
    summary=dict(metrics=metrics,same_payloads=True,packets=len(payloads[0]),negative_controls_rejected=True,
        difference_counts={k:{field:len(v) for field,v in d.items()} for k,d in changes.items()},
        text_checks={k:{field:r[field] for field in ('counts','source_changes','no_publication_regression')} for k,r in text.items()},release_ready=False)
    if any(sha(Path(p))!=h for p,h in sources.items()):raise ValueError('Changed source')
    report=dict(summary=summary,changed_frames=changes,text_records={k:r['records'] for k,r in text.items()},sources=sources,
        artifacts={p.name:sha(p) for p in out.iterdir()},scope=__doc__)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(packets=summary['packets'],same_payloads=True,differences=summary['difference_counts'])))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True)
    review(**vars(p.parse_args()))
