"""Publish actual camera-store timing with unchanged source-frame strips."""
import argparse
import hashlib
from html import escape
import json
from pathlib import Path

from PIL import Image

from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha,verify_capture


def frame_panel(root,row):
    path=root/row['frame_image']
    if sha(path)!=row['frame_image_sha256']:
        raise ValueError('Changed source PNG')
    with Image.open(path) as image:
        if hashlib.sha256(image.convert('RGB').tobytes()).hexdigest()!=row['video_sha256']:
            raise ValueError('PNG differs from captured video')
    return path


def publish(park,route,capture,out):
    p=bound_report(park);r=bound_report(route);receipt,rows=verify_capture(capture)
    if (r['sources'].get(str(park))!=sha(park) or
            p['sources'].get(str(capture/'capture.json'))!=sha(capture/'capture.json') or
            not p['observer_neutral'] or not r['observer_neutral']):
        raise ValueError('Need common neutral store/renderer proofs')
    sources={str(v):sha(v) for v in (park,route,capture/'capture.json',
        capture/'timeline.json',Path(__file__),Path('tools/benchmark_report.py'))}
    panels={};strips=[];selected=[]
    for room in range(4):
        # Fixed policy: first qualified changed store in each room, not best-looking.
        event=next(e for e in r['events'] if e['phase'].startswith(f'room{room}.'))
        selected.append(event)
        series={v['frame']:v['camera'] for v in r['phases'][event['phase']]['series']}
        figures=[]
        for frame in range(event['store_frame']-1,event['display_frame']+1):
            path=frame_panel(capture,rows[frame-1]);panels[str(path)]=sha(path)
            if frame==event['store_frame']:
                label=f'Store {event["camera"]}, scanline {event["store_line"]}'
            elif frame==event['display_frame']:label='New camera visible'
            else:label='Before store'
            figures.append(f'<figure><img src="../{escape(capture.name)}/{escape(rows[frame-1]["frame_image"])}" '
                f'alt="Room {room}, frame {frame}"><figcaption>{escape(label)}<br>'
                f'Frame {frame} · rendered camera {series[frame]}</figcaption></figure>')
        strips.append(f'<h3>Room {room}: camera {event["camera"]}</h3><div class="strip">'+''.join(figures)+'</div>')
    table=''.join(f'<tr><td>{room}</td><td>{r["room_events"][str(room)]}</td></tr>' for room in range(4))
    nes_exceptions=[e for e in p['nes']['events'] if e['store_to_display']==0]
    exceptions=''.join(f'<tr><td>{e["store_frame"]}</td><td>{e["store_line"]}</td>'
        f'<td>{e["camera"]}</td><td>{e["display_frame"]}</td></tr>' for e in nes_exceptions)
    summary='<table><tr><th>Capture</th><th>Same-frame display</th><th>Next-frame display</th><th>Missing display</th></tr>'
    for label,data in (('Original NES, park',p['nes']),('SNES, park',p['snes']),('SNES, four rooms',r)):
        summary+=f'<tr><td>{label}</td><td>{data["store_to_display"].get("0",0)}</td>'
        summary+=f'<td>{data["store_to_display"].get("1",0)}</td><td>{data["missing_display"]}</td></tr>'
    summary+='</table>'
    page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>RCR · actual camera-store to display latency</title><style>body{background:#101821;color:#eef;font:17px system-ui;max-width:1200px;margin:auto;padding:24px}a{color:#9df}td,th{padding:9px;border:1px solid #567}table{border-collapse:collapse}.strip{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}figure{margin:0}img{width:100%;image-rendering:pixelated}.open{color:#ffd68b}</style>
<h1>Camera committed → camera actually displayed</h1>
<p>September 18, 2026 · current ROM 071c89e unchanged · no Rival input or restart.</p>
<p>New host-only observation records the actual accumulator and high camera bit immediately before STA $F6. Exact instructions, caller stacks, completed main/input/store/finish chains, and independent full-renderer observations are checked. The entire 8,934-frame timeline and WAV match the normal run.</p>
'''+summary+'''
<p>Four-room coverage includes 7,211 stable rendered frames and 930 changed camera commits. All 160 street scanlines must agree; missing or split coverage fails. Unchanged cameras, transitions, single-frame segments, and censored boundaries remain in the reports. Four nested transition camera writes are retained separately.</p>
<table><tr><th>Room</th><th>Qualified changes</th></tr>'''+table+'''</table>
<h2>Original NES exceptions remain visible</h2>
<table><tr><th>Store frame</th><th>Store scanline</th><th>Camera</th><th>Display frame</th></tr>'''+exceptions+'''</table>
<p class="open">The original NES has three same-frame park updates that the SNES sample does not. Different encounters prevent event-for-event comparison. The SNES matches the usual next-frame delay, not every original timing case. Full-route original-NES store/display equivalence and input-to-display latency remain unverified.</p>
<h2>Unaltered source-frame strips</h2>
<p>First qualified changed commit in each room. Each full-frame PNG is verified against its recorded PNG hash and raw video RGB hash; no crops, alignment, redrawing, or generated graphics. Rendered camera labels come from every street scanline, not image matching.</p>
'''+''.join(strips)+'''
<h2>What this does not clear</h2>
<p class="open">The existing strict background audit still fails its same-frame RAM publication rule at 885 observations. No gate was waived. These measurements distinguish actual display latency from frame-end bookkeeping; they do not prove full-game speed or resolve the physical audio gaps. No new test ROM is claimed.</p>
<p><a href="../triangle-game-store-latency-985/report.json">Park comparison and complete sparse chains</a> · <a href="../triangle-route-store-latency-986/report.json">Four-room renderer joins and all exclusions</a> · <a href="../triangle-route-review-980/">Exact backgrounds and loop cadence</a> · <a href="../triangle-game-physical-context-973/">Unresolved physical audio evidence</a> · <a href="report.json">Bound sources and panel hashes</a></p></html>'''
    out.mkdir(parents=True,exist_ok=False)
    (out/'index.html').write_text(page)
    (out/'report.json').write_text(json.dumps(dict(sources=sources,panels=panels,
        selected_events=selected,nes_same_frame_events=nes_exceptions,
        page_sha256=sha(out/'index.html'),release_ready=False),indent=2)+'\n')
    print(json.dumps(dict(out=str(out),panels=len(panels),sources=len(sources))))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('park','route','capture','out'):parser.add_argument('--'+name,type=Path,required=True)
    publish(**vars(parser.parse_args()))
