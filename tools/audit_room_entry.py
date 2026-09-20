"""Compare room-entry visibility at fixed offsets from rendering-enable edges."""
import argparse
import html
import json
from pathlib import Path
import shutil

import numpy as np

try:
    from .benchmark_report import verify_capture, sha
    from .audit_scroll_publication import frame_path, rgb555, BACKGROUND_REGION
except ImportError:
    from benchmark_report import verify_capture, sha
    from audit_scroll_publication import frame_path, rgb555, BACKGROUND_REGION

ROOMS=(1,2,3)
WINDOW=40


def rendering_mask(row):
    return row['native']['ppu_mask'] if 'native' in row else row['nes_ppu']['mask']


def load_anchors(rows, enable):
    """Find state edges, never a favorable image or a later re-entry."""
    room=bytes.fromhex(rows[enable]['game_ram_hex'])[0x42]
    change=enable
    while change>0 and bytes.fromhex(rows[change-1]['game_ram_hex'])[0x42]==room:
        change-=1
    off=enable
    while off>0 and not rendering_mask(rows[off-1])&8:
        off-=1
    if change==0 or off==0 or off==enable:
        raise ValueError('Need observed room-change and rendering-off edges before entry')
    if any(rows[i]['frame']!=rows[i-1]['frame']+1 for i in range(min(change,off),enable+1)):
        raise ValueError('Load timeline is not consecutive')
    return dict(room_change_frame=rows[change]['frame'],rendering_off_frame=rows[off]['frame'],
                enable_frame=rows[enable]['frame'])


def visibility_latencies(anchors, first_nonblack_offset):
    visible=None if first_nonblack_offset is None else anchors['enable_frame']+first_nonblack_offset
    return dict(first_visible_frame=visible,
        room_change_to_visible=None if visible is None else visible-anchors['room_change_frame'],
        rendering_off_to_visible=None if visible is None else visible-anchors['rendering_off_frame'])


def no_later(reference,candidate,key):
    return reference[key] is not None and candidate[key] is not None and candidate[key]<=reference[key]


def entries(rows):
    result={}
    previous=0
    for i,row in enumerate(rows):
        mask=rendering_mask(row)
        raw=bytes.fromhex(row['game_ram_hex'])
        room=raw[0x42]
        if mask&8 and not previous&8 and room in ROOMS and raw[0x100]==0xc0:
            result.setdefault(room,i)
        previous=mask
    if set(result)!=set(ROOMS):raise ValueError('Need first rendering-enable edge in rooms 1, 2 and 3')
    return result


def audit(reference,candidate,out):
    loaded=[verify_capture(p) for p in (reference,candidate)]
    for system,(r,rows) in zip(('nes','snes'),loaded):
        if (r['system']!=system or not r['capture_complete'] or not r['frame_images']
                or any(x['fault'] or x['input_requested']!=x['input_delivered'] for x in rows)):
            raise ValueError('Need complete fault-free frame captures')
    if (loaded[0][0]['scenario_sha256']!=loaded[1][0]['scenario_sha256']
            or loaded[0][0]['rom_sha256']!=loaded[1][0]['templates']['menu']['source_rom']):
        raise ValueError('Input scenarios differ')
    indexes=[entries(rows) for r,rows in loaded]
    out.mkdir(parents=True,exist_ok=False)
    comparisons=[];cards=[]
    x0,y0,x1,y1=BACKGROUND_REGION
    for room in ROOMS:
        samples=[];paths=[]
        for root,(receipt,rows),index in zip((reference,candidate),loaded,indexes):
            selected=rows[index[room]:index[room]+WINDOW]
            if len(selected)!=WINDOW or any(bytes.fromhex(x['game_ram_hex'])[0x42]!=room for x in selected):
                raise ValueError('Entry window leaves its room or is truncated')
            ps=[frame_path(root,x) for x in selected]
            pixels=[rgb555(p)[y0:y1,x0:x1] for p in ps]
            samples.append(dict(enable_frame=selected[0]['frame'],
                first_nonblack_offset=next((i for i,a in enumerate(pixels) if np.any(a)),None),
                brightness=[round(float(a.mean()),4) for a in pixels],
                native_hidden_frames=sum(x.get('native',{}).get('transition_state',0)==2 for x in selected),
                palette_shadow=[bytes.fromhex(x['game_ram_hex'])[0x110:0x130].hex() for x in selected]))
            anchors=load_anchors(rows,index[room])
            samples[-1].update(anchors)
            samples[-1].update(visibility_latencies(anchors,samples[-1]['first_nonblack_offset']))
            paths.append((ps,pixels))
        differences=[int(np.any(a!=b,axis=2).sum()) for a,b in zip(paths[0][1],paths[1][1])]
        a,b=samples
        comparisons.append(dict(room=room,nes=a,snes=b,mismatch_pixels_by_offset=differences,
            first_visible_no_later=a['first_nonblack_offset'] is not None and b['first_nonblack_offset'] is not None
                and b['first_nonblack_offset']<=a['first_nonblack_offset'],
            room_change_to_visible_no_later=no_later(a,b,'room_change_to_visible'),
            rendering_off_to_visible_no_later=no_later(a,b,'rendering_off_to_visible'),
            all_fixed_offset_backgrounds_exact=not any(differences)))
        cards.append(f'<h2>Room {room}</h2>')
        cards.append('<table><tr><th>Frames to first scenery pixels</th><th>NES</th><th>SNES</th></tr>'+''.join(
            f'<tr><td>{label}</td><td>{a[key]}</td><td>{b[key]}</td></tr>' for key,label in (
                ('room_change_to_visible','From room change'),('rendering_off_to_visible','From rendering off'),
                ('first_nonblack_offset','From rendering on')) )+'</table>')
        for offset in (0,7,10,14,18,24,29,39):
            cards.append(f'<h3>Rendering-enable +{offset} frames</h3><section>')
            for label,(ps,pixels) in zip(('nes','snes'),paths):
                target=f'room-{room}-{offset:02d}-{label}.png'
                shutil.copyfile(ps[offset],out/target)
                cards.append(f'<figure><img loading="lazy" src="{target}"><figcaption>{label}</figcaption></figure>')
            cards.append('</section>')
    gates=dict(first_visible_no_later=all(x['first_visible_no_later'] for x in comparisons),
        room_change_to_visible_no_later=all(x['room_change_to_visible_no_later'] for x in comparisons),
        rendering_off_to_visible_no_later=all(x['rendering_off_to_visible_no_later'] for x in comparisons),
        every_fixed_offset_background_exact=all(x['all_fixed_offset_backgrounds_exact'] for x in comparisons))
    report=dict(passed=all(gates.values()),gates=gates,comparisons=comparisons,
        sources={s:dict(rom_sha256=r['rom_sha256'],capture_sha256=sha(p/'capture.json')) for s,p,(r,_) in zip(('nes','snes'),(reference,candidate),loaded)},
        audit_sha256=sha(Path(__file__)),scope='Forty fixed frame offsets from the first PPU rendering-enable edge in each room. '
        'First nonblack fixed-band pixel measures visibility latency, not selected alignment. Palette shadows and every pixel mismatch retained. '
        'Total visibility latency is also gated from observed room-change and rendering-off edges; moving work before rendering-enable cannot hide it. '
        'No phase search, threshold relaxation or actor matching. This is a room-entry/fade check, not full-game speed.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Room entry and fade</title>'
        '<style>body{background:#101821;color:#eee;font:17px system-ui;margin:30px}a{color:#9df}section{display:flex}img{width:512px;image-rendering:pixelated}</style>'
        f'<h1>Room entry: {"PASS" if report["passed"] else "FAIL"}</h1><p>'+html.escape(report['scope'])+
        '</p><p><a href="report.json">Full measurements and hashes</a></p>'+''.join(cards))
    print(json.dumps(dict(passed=report['passed'],gates=gates,visibility=[dict(room=x['room'],nes=x['nes']['first_nonblack_offset'],snes=x['snes']['first_nonblack_offset']) for x in comparisons]),indent=2))
    return report['passed']


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('reference','candidate','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();raise SystemExit(0 if audit(a.reference,a.candidate,a.out) else 1)
