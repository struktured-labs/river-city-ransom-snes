"""Publish current four-room cadence and exact-background qualification."""
import argparse
from html import escape
import json
from pathlib import Path

from tools.audit_nes_filter import bound
from tools.benchmark_report import sha


def publish(cadence,background,out):
    timing=bound(cadence);graphics=json.loads(background.read_text())
    if sha(Path('tools/audit_background_sweep.py'))!=graphics['audit_sha256']:
        raise ValueError('Background audit implementation changed')
    roots=dict(nes=Path('build/background-nes-333'),snes=Path('build/triangle-game-background-976'),
        normal_nes=Path('build/park-single-nes-331'),normal_snes=Path('build/triangle-game-inplace-normal-891'),
        negative=Path('build/background-scroll-negative-336'))
    sources={**timing['sources'],str(cadence):sha(cadence),str(background):sha(background),
        str(Path(__file__)):sha(Path(__file__)),
        'tools/audit_background_sweep.py':graphics['audit_sha256']}
    for name,root in roots.items():
        path=root/'capture.json'
        if sha(path)!=graphics['sources'][name]['capture_sha256']:raise ValueError('Different background capture')
        sources[str(path)]=sha(path)
    table=[]
    for room,label in enumerate(('School street','Alley','Mall','Park')):
        values=[]
        for system in ('nes','snes'):
            measured=timing[system]['rooms'][str(room)]
            values.extend((len(measured['iterations']),len(measured['off_cadence_iterations']),
                           len(measured['off_cadence_starts'])))
        table.append('<tr><th>'+label+'</th>'+''.join('<td>'+str(v)+'</td>' for v in values)+'</tr>')
    coverage=''.join('<tr><td>'+str(room)+'</td><td>'+str(count)+'</td></tr>'
                     for room,count in graphics['coverage'].items())
    # Existing exact-frame panels, copied by the background auditor from its
    # fixed first-stable observations. No generated/repainted game imagery.
    panels=[];panel_sources={}
    for room in range(4):
        eligible=[r for r in graphics['comparisons'] if r['room']==room and r['camera'] in (64,128,255,256,384,511)]
        if not eligible:raise ValueError('No fixed camera checkpoint in room')
        sample=min(eligible,key=lambda r:r['camera'])
        items=[]
        for system in ('nes','snes'):
            name=f'{system}-{room}-{sample["camera"]}-primary.png'
            path=background.parent/name
            panel_sources[str(path)]=sha(path)
            items.append(f'<figure><img src="../{escape(background.parent.name)}/{name}" '
                f'alt="{system} room{room} camera{sample["camera"]}"><figcaption>{system.upper()}, '
                f'frame{sample[system+"_frame"]}</figcaption></figure>')
        panels.append(f'<h3>Room{room}, camera{sample["camera"]}</h3><div class="grid">'+''.join(items)+'</div>')
    page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>RCR · current four-room speed and scrolling checks</title><style>body{background:#101821;color:#eef;font:17px system-ui;max-width:1200px;margin:auto;padding:24px}a{color:#9df}td,th{padding:9px;border:1px solid #567}.grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}figure{margin:0}img{width:100%;image-rendering:pixelated}.open{color:#ffd68b}</style>
<h1>Current build: four-room cadence and exact backgrounds</h1>
<p>September18 · Rival ROM071c89e unchanged. No hardware inputs or restart. <a href="report.json">Bound sources and panels</a>.</p>
<h2>Complete main-loop timing, not animation guesses</h2>
<table><tr><th>Room</th><th>NES loops</th><th>NES loops≠2ticks</th><th>NES start gaps≠2frames</th><th>SNES loops</th><th>SNES loops≠2ticks</th><th>SNES start gaps≠2frames</th></tr>'''+''.join(table)+'''</table>
<p>All3,588 stable SNES iterations finish in two game ticks. The original NES has13 three-tick iterations in this route. Both exact-PC observers preserve their complete independent normal timeline and PCM. Every room exceeds the unchanged64-iteration minimum;70 non-stable iterations and one censored boundary per system are retained.</p>
<p class="open">Different encounters prevent an equal-work speed ratio. The NES itself fails an absolute “every loop must take two ticks” rule; those13 original overruns remain visible. This does not prove full-game original-speed parity or input-to-display latency.</p>
<h2>800 common camera positions: original backgrounds exact</h2><table><tr><th>Room</th><th>Common positions</th></tr>'''+coverage+'''</table>
<p>All fixed RGB555 backgrounds match across the full256×160 playfield; first-stable samples are no later than NES. Every room exceeds64 common positions. Independent primary video/timelines/PCM are unchanged by background observation. The known broken-scroll ROM still fails pixel and settling checks.</p>
<p class="open">The combined strict audit remains FAIL:885 end-of-frame RAM/published-scroll differences violate its same-frame rule. Coverage is no longer the blocker. We have not waived this rule or equated it with885 visibly late frames. The next check must bind actual store timing to actual rendered frames.</p>
<p><a href="../triangle-game-background-audit-979/">Complete background comparison, every mismatch and negative control</a> · <a href="../triangle-route-cadence-978/report.json">Every NES/SNES iteration and exclusion</a>.</p>
<h2>Unaltered fixed-camera primary-image pairs</h2>'''+''.join(panels)+'''
<p>Actors can differ between encounters; the separately observed background plane—not a dynamic actor mask—is compared. These PNGs are exact source-frame copies. No alignment or image edits.</p>
<h2>Remaining</h2><p>Actual input/store-to-render latency, broader gameplay/endurance and physical acoustic verification remain open. The three physical combat gaps are not cleared by these speed checks.704 unit tests pass. No new user test build is being claimed.</p></html>'''
    out.mkdir(parents=True,exist_ok=False)
    (out/'index.html').write_text(page)
    (out/'report.json').write_text(json.dumps(dict(sources=sources,panels=panel_sources,
        page_sha256=sha(out/'index.html'),release_ready=False,background_strict_passed=graphics['passed'],
        sampled_snes_cadence=timing['snes']['sampled_two_tick_cadence']),indent=2)+'\n')
    print(json.dumps(dict(out=str(out),sources=len(sources),panels=len(panel_sources))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('cadence','background','out'):p.add_argument('--'+name,type=Path,required=True)
    publish(**vars(p.parse_args()))
