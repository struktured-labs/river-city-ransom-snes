"""First actual alley-to-school return against NES, without substituting startup."""
import argparse
import html
import json
from pathlib import Path
import shutil

import numpy as np

from tools.audit_main_display_latency import bound_report
from tools.audit_room_entry import rendering_mask,load_anchors,visibility_latencies,no_later
from tools.audit_scroll_publication import BACKGROUND_REGION,frame_path,rgb555
from tools.benchmark_report import sha,verify_capture
from tools.school_return_campaign import installed


def first_return(rows):
    rooms=[bytes.fromhex(r['game_ram_hex'])[0x42] for r in rows]
    change=next((i for i in range(1,len(rows)) if rooms[i-1]==1 and rooms[i]==0),None)
    if change is None:raise ValueError('No actual alley-to-school return')
    enable=next((i for i in range(change,len(rows)) if rendering_mask(rows[i])&8
                 and not rendering_mask(rows[i-1])&8),None)
    if enable is None or enable+40>len(rows) or any(rooms[i]!=0 for i in range(change,enable+40)):
        raise ValueError('First return fade is incomplete; no later-entry fallback')
    anchors=load_anchors(rows,enable)
    if anchors['room_change_frame']!=rows[change]['frame']:
        raise ValueError('First return and rendering edge belong to different entries')
    return enable,anchors


def audit(reference,candidate,out):
    if out.exists():raise ValueError('Fresh review required')
    captures=[];sources={}
    with installed():
        for root in (reference,candidate):
            binding=bound_report(root/'school-return-report.json')
            sources.update(binding['sources'])
            captures.append(verify_capture(root))
    if (captures[0][0]['system']!='nes' or captures[1][0]['system']!='snes' or
            captures[0][0]['scenario_sha256']!=captures[1][0]['scenario_sha256'] or
            captures[0][0]['rom_sha256']!=captures[1][0]['templates']['menu']['source_rom']):
        raise ValueError('Different original game or input policy')
    out.mkdir(parents=True)
    results={};pictures=[]
    x0,y0,x1,y1=BACKGROUND_REGION
    for label,root,(receipt,rows) in zip(('nes','snes'),(reference,candidate),captures):
        if not receipt['capture_complete'] or any(r['fault'] or r['input_requested']!=r['input_delivered'] for r in rows):
            raise ValueError('Incomplete/faulty game episode')
        index,anchors=first_return(rows)
        paths=[frame_path(root,r) for r in rows[index:index+40]]
        pixels=[rgb555(p)[y0:y1,x0:x1] for p in paths]
        visible=next((i for i,p in enumerate(pixels) if np.any(p)),None)
        results[label]=dict(**anchors,first_nonblack_offset=visible,**visibility_latencies(anchors,visible),
            palette_shadow=[bytes.fromhex(r['game_ram_hex'])[0x110:0x130].hex() for r in rows[index:index+40]],
            camera=[int.from_bytes(bytes.fromhex(r['game_ram_hex'])[0xdc:0xde],'little') for r in rows[index:index+40]])
        pictures.append(pixels)
        for p in (root/'school-return-report.json',root/'capture.json',root/'timeline.json',*paths):
            sources[str(p)]=sha(p)
        for offset in (0,7,9,14,18,24,29,39):
            shutil.copyfile(paths[offset],out/f'{label}-{offset:02d}.png')
    differences=[int(np.any(a!=b,axis=2).sum()) for a,b in zip(*pictures)]
    a,b=results['nes'],results['snes']
    gates=dict(fixed_fades_exact=not any(differences),
        first_visible_no_later=no_later(a,b,'first_nonblack_offset'),
        room_change_no_later=no_later(a,b,'room_change_to_visible'),
        rendering_off_no_later=no_later(a,b,'rendering_off_to_visible'))
    for p in (Path(__file__),Path('tools/school_return_campaign.py'),Path('tools/audit_room_entry.py'),
              Path('tools/audit_scroll_publication.py'),Path('tools/benchmark_report.py')):
        sources[str(p)]=sha(p)
    report=dict(passed=all(gates.values()),gates=gates,samples=results,mismatch_pixels_by_offset=differences,
        sources=sources,release_ready=False,equal_encounters=False,
        scope='First actual room1-to-room0 return, same read-only navigation policy on independent NES/SNES games. '
        'First rendering-enable edge and all40 fixed background offsets; full room/off visibility latency retained. '
        'Initial school startup cannot substitute for a return. Not identical encounters, exact CPU work or audio certification.')
    page='<!doctype html><meta charset="utf-8"><title>School return versus NES</title><style>body{background:#101820;color:#eef;font:17px system-ui;max-width:1100px;margin:30px auto}a{color:#8df}.grid{display:grid;grid-template-columns:1fr 1fr}img{width:100%}pre{white-space:pre-wrap}</style>'
    page+=f'<h1>School-return visibility: {"PASS" if report["passed"] else "FAIL"}</h1><p>'+html.escape(report['scope'])+'</p><a href="report.json">All measurements and hashes</a>'
    page+='<pre>'+html.escape(json.dumps({k:{n:v[n] for n in ('room_change_to_visible','rendering_off_to_visible','first_nonblack_offset')} for k,v in results.items()},indent=2))+'</pre>'
    for offset in (0,7,9,14,18,24,29,39):
        page+=f'<h2>Enable +{offset}</h2><div class="grid">'+''.join(f'<figure><img src="{label}-{offset:02d}.png"><figcaption>{label}</figcaption></figure>' for label in ('nes','snes'))+'</div>'
    (out/'index.html').write_text(page)
    report['artifacts']={p.name:sha(p) for p in out.iterdir()}
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=report['passed'],gates=gates,visibility={k:{n:v[n] for n in ('room_change_to_visible','rendering_off_to_visible','first_nonblack_offset')} for k,v in results.items()})))
    return report['passed']


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('reference','candidate','out'):p.add_argument('--'+name,type=Path,required=True)
    raise SystemExit(0 if audit(**vars(p.parse_args())) else 1)
