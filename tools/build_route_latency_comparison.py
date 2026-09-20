"""Publish full-route NES/SNES camera latency without matching encounters."""
import argparse
from collections import Counter
from html import escape
import json
import os
from pathlib import Path

from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha,verify_capture
from tools.build_store_latency_review import frame_panel


def histogram(events,key):
    return dict(sorted(Counter(str(e[key]) for e in events).items()))


def publish(nes,snes,nes_capture,snes_capture,sensitivity,out):
    reports={s:bound_report(p) for s,p in (('nes',nes),('snes',snes))}
    roots=dict(nes=nes_capture,snes=snes_capture)
    mutants=bound_report(sensitivity)
    if mutants['sources'].get(str(snes))!=sha(snes) or not mutants['all_detected']:
        raise ValueError('Missing current-route sensitivity proof')
    rows={};receipts={};panels={};sources={};table=[];strips=[];selections=[]
    for system,root in roots.items():
        receipts[system],rows[system]=verify_capture(root)
        sources.update({str(root/'capture.json'):sha(root/'capture.json'),
                        str(root/'timeline.json'):sha(root/'timeline.json')})
        if not reports[system]['observer_neutral']:raise ValueError('Non-neutral report')
    # The SNES route report binds a separate render capture, whose common normal
    # is also bound by the actual pre-store report. Verify that chain explicitly.
    if reports['nes']['sources'].get(str(nes_capture/'capture.json'))!=sha(nes_capture/'capture.json'):
        raise ValueError('Different NES capture')
    mains=[Path(p) for p in reports['snes']['sources'] if p.endswith('/report.json')]
    if len(mains)!=1:raise ValueError('Ambiguous SNES main proof')
    main=bound_report(mains[0])
    if main['sources'].get(str(snes_capture/'capture.json'))!=sha(snes_capture/'capture.json'):
        raise ValueError('Different SNES capture')
    if receipts['nes']['scenario_sha256']!=receipts['snes']['scenario_sha256']:
        raise ValueError('Different route policy')
    def url(path):return escape(os.path.relpath(path,out))
    for room in range(4):
        cells=[str(room)]
        for system in ('nes','snes'):
            report=reports[system]
            events=[e for e in report['events'] if e['phase'].startswith(f'room{room}.')]
            cells.extend((str(len(events)),escape(json.dumps(histogram(events,'store_to_display'))),
                          escape(json.dumps(histogram(events,'start_to_display')))))
            # First qualified change, not selected for latency or appearance.
            event=events[0];selections.append(dict(system=system,**event))
            series={r['frame']:r['camera'] for r in report['phases'][event['phase']]['series']}
            figures=[]
            for frame in range(event['store_frame']-1,event['store_frame']+2):
                row=rows[system][frame-1];path=frame_panel(roots[system],row)
                panels[str(path)]=sha(path)
                label='store' if frame==event['store_frame'] else ('before' if frame<event['store_frame'] else 'after')
                figures.append(f'<figure><img src="{url(path)}" alt="{system}, room {room}, frame {frame}">'
                    f'<figcaption>{label}: frame {frame}, actual camera {series[frame]}</figcaption></figure>')
            strips.append(f'<h3>{system.upper()}, room {room}: store {event["camera"]} '
                f'at line {event["store_line"]}, display delay {event["store_to_display"]} frame(s)</h3>'
                '<div class="strip">'+''.join(figures)+'</div>')
        table.append('<tr>'+''.join('<td>'+c+'</td>' for c in cells)+'</tr>')
    summary={s:{k:r[k] for k in ('rendered_frames','room_events','store_to_display','start_to_display','missing_display')}
             for s,r in reports.items()}
    body='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>RCR · full-route original camera latency comparison</title><style>body{background:#101821;color:#eef;font:17px system-ui;max-width:1200px;margin:auto;padding:24px}a{color:#9df}td,th{padding:9px;border:1px solid #567}table{border-collapse:collapse}.strip{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}figure{margin:0}img{width:100%;image-rendering:pixelated}.open{color:#ffd68b}pre{white-space:pre-wrap}</style>
<h1>Full-route original NES versus current SNES camera latency</h1>
<p>September 18, 2026 · current ROM 071c89e unchanged · no Rival input/restart.</p>
<p>Each observer preserves its entire independent baseline timeline and WAV. Camera values come from the actual pre-store accumulator/high bit and all actual rendered street fetches: 32 eight-pixel groups on each of 160 NES lines; all 160 SNES lines. Identical stable-gameplay predicates select each room. No fitted lag, dropped late event, or matched-encounter claim.</p>
<table><tr><th>Room</th><th>NES changes</th><th>NES store → display</th><th>NES start → display</th><th>SNES changes</th><th>SNES store → display</th><th>SNES start → display</th></tr>'''+''.join(table)+'''</table>
<p>Histogram keys are frames; values count qualified changed stores. “Start” means observed game-loop start, not physical input. Missing display is counted separately, not assigned a finite delay. Boundary and unchanged-camera exclusions remain in each raw report.</p>
<p>The mall illustrates why both clocks matter: the original NES often stores the camera in its next host frame and displays it that frame. The port stores during its starting frame and displays the next frame. A larger store-to-display count therefore does not automatically mean a larger game-loop-start-to-display count. These are measured independent encounters, not paired identical inputs.</p><pre>'''+escape(json.dumps(summary,indent=2))+'''</pre>
<p class="open">Encounters and route lengths differ. This compares within-system commit/display timing, not equal-work combat speed, physical input latency, or full-game completion. The earlier same-frame RAM publication gate remains failed and has not been waived. Physical combat audio gaps remain unresolved.</p>
<p>Eight synthetic sensitivity checks inject one extra display frame and a missing camera into copies of the first qualified SNES event in each room. All eight are detected exactly. Original traces, images, and ROM are unchanged. <a href="'''+url(sensitivity)+'''">Every mutation and observed result</a>.</p>
<h2>Unaltered before/store/after frame strips</h2><p>First qualified change in each room and system. Original full-frame PNGs, verified both by file hash and captured video RGB hash. No artwork edits, fitted shifts or dynamic actor masks.</p>'''+''.join(strips)+'''
<p><a href="'''+url(nes)+'''">Complete original-NES report</a> · <a href="'''+url(snes)+'''">Complete SNES report</a> · <a href="report.json">Source and panel manifest</a> · <a href="../triangle-route-review-980/">Exact backgrounds and main-loop cadence</a> · <a href="../triangle-game-physical-context-973/">Open physical-audio evidence</a></p></html>'''
    sources.update({str(p):sha(p) for p in (nes,snes,sensitivity,mains[0],Path(__file__),
        Path('tools/build_store_latency_review.py'),Path('tools/benchmark_report.py'))})
    out.mkdir(parents=True,exist_ok=False);(out/'index.html').write_text(body)
    (out/'report.json').write_text(json.dumps(dict(sources=sources,panels=panels,summary=summary,
        selected_events=selections,page_sha256=sha(out/'index.html'),release_ready=False),indent=2)+'\n')
    print(json.dumps(dict(out=str(out),panels=len(panels),sources=len(sources))))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('nes','snes','nes-capture','snes-capture','sensitivity','out'):parser.add_argument('--'+name,type=Path,required=True)
    publish(**vars(parser.parse_args()))
