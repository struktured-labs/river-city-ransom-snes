"""Measure complete fade generations through observed shadow/prepared palettes."""
import argparse
import html
import json
from pathlib import Path
import re
import struct

import numpy as np

try:
    from .benchmark_report import verify_capture, sha
    from .audit_room_entry import entries, WINDOW, ROOMS
    from .audit_scroll_publication import frame_path, rgb555, BACKGROUND_REGION
except ImportError:
    from benchmark_report import verify_capture, sha
    from audit_room_entry import entries, WINDOW, ROOMS
    from audit_scroll_publication import frame_path, rgb555, BACKGROUND_REGION


def canonical_palette(source):
    if len(source)!=32:raise ValueError('Need all 32 original palette bytes')
    result=bytearray(32)
    for i,value in enumerate(source):result[i-16 if i in (16,20,24,28) else i]=value
    return result


def bg_words(shadow,colors):
    return tuple(colors[shadow[0 if i%4==0 else i]&63] for i in range(16))


def generations(rows,colors):
    found={}
    for offset,row in enumerate(rows):
        raw=bytes.fromhex(row['game_ram_hex']);level=raw[0x692]
        if level in range(4) and raw[0x3e]&8:
            found.setdefault(level,dict(offset=offset,frame=row['frame'],
                source_indices=canonical_palette(raw[0x110:0x130])[:16].hex(),
                words=bg_words(canonical_palette(raw[0x110:0x130]),colors)))
    if set(found)!=set(range(4)):raise ValueError('Need four completed, dirty-flagged fade generations')
    if [found[i]['offset'] for i in range(4)]!=sorted(v['offset'] for v in found.values()):
        raise ValueError('Fade generations are not ordered')
    return found


def delivery_offsets(native,generation,repeated_rgb=False):
    """Frame-end observations, not a claim about intra-frame CGRAM writes."""
    start=generation['offset'];wanted=generation['words'];result={}
    for name in ('ppu_shadow','prepared_source','prepared_bg'):
        if name=='prepared_bg' and repeated_rgb:
            result[name]=None
            continue
        result[name]=next((i for i in range(start,len(native)) if (
            tuple(struct.unpack('<16H',bytes.fromhex(native[i]['snes_palette'][name]))) if name=='prepared_bg'
            else native[i]['snes_palette'][name][:32])==(
                wanted if name=='prepared_bg' else generation['source_indices'])),None)
        if result[name] is None:raise ValueError('Generated palette never reached '+name)
    ordered=[v for v in result.values() if v is not None]
    if ordered!=sorted(ordered):raise ValueError('Palette stages delivered out of order')
    return result


def audit(reference,candidate,normal,rom,palette,labels,out):
    loaded=[verify_capture(p) for p in (reference,candidate,normal)]
    nes,observed,control=[item[0] for item in loaded]
    if nes['system']!='nes' or observed['system']!='snes' or not observed.get('snes_palette_observer'):
        raise ValueError('Need NES reference and bound native palette observations')
    if any(not r['capture_complete'] or any(x['fault'] or x['input_requested']!=x['input_delivered'] for x in rows) for r,rows in loaded):
        raise ValueError('Incomplete or faulty inputs')
    for key in ('rom_sha256','scenario_sha256','audio_sha256','frames'):
        if observed[key]!=control[key]:raise ValueError('Palette observer changed '+key)
    stripped=[{k:v for k,v in r.items() if k!='snes_palette'} for r in loaded[1][1]]
    if stripped!=loaded[2][1]:raise ValueError('Palette observer changed existing timeline fields')
    if (nes['scenario_sha256']!=observed['scenario_sha256'] or
        observed['templates']['menu']['source_rom']!=nes['rom_sha256']):raise ValueError('Different source scenario/ROM')
    if sha(rom)!=observed['rom_sha256']:raise ValueError('Wrong palette ROM')
    colors=[int(s,16) for s in re.findall(r'\$([0-9A-Fa-f]{4})',palette.read_text())]
    addresses=[int(r.split()[1],16) for r in labels.read_text().splitlines() if r.split()[2]=='.native_palette']
    if len(colors)!=64 or len(addresses)!=1 or rom.read_bytes()[addresses[0]:addresses[0]+128]!=struct.pack('<64H',*colors):
        raise ValueError('Palette lookup is not bound to the actual candidate ROM')
    indexes=[entries(rows) for _,rows in loaded[:2]]
    rooms=[];tables=[]
    for room in ROOMS:
        windows=[rows[index[room]:index[room]+WINDOW] for (_,rows),index in zip(loaded[:2],indexes)]
        if any(len(w)!=WINDOW or any(bytes.fromhex(r['game_ram_hex'])[0x42]!=room for r in w) for w in windows):
            raise ValueError('Truncated or changed-room fade window')
        gens=[generations(w,colors) for w in windows]
        native=windows[1];steps=[]
        for level in range(4):
            a,b=[g[level] for g in gens]
            if a['words']!=b['words'] or a['source_indices']!=b['source_indices']:raise ValueError('Original and candidate generated different fade colors')
            wanted=b['words'];start=b['offset']
            repeated_rgb=any(gens[1][prior]['words']==wanted for prior in range(level))
            stage_matches=delivery_offsets(native,b,repeated_rgb)
            steps.append(dict(level=level,nes_generation_offset=a['offset'],snes_generation_offset=start,
                delivery_offsets=stage_matches,from_generation={k:None if v is None else v-start for k,v in stage_matches.items()},
                prepared_bg_ambiguous_same_rgb_as_prior_level=repeated_rgb,
                palette_words=wanted))
        x0,y0,x1,y1=BACKGROUND_REGION
        visible=[]
        for root,w in zip((reference,candidate),windows):
            visible.append(next((i for i,r in enumerate(w) if np.any(rgb555(frame_path(root,r))[y0:y1,x0:x1])),None))
        rooms.append(dict(room=room,steps=steps,first_nonblack_band_offsets=dict(nes=visible[0],snes=visible[1]),
            native_timeline=[dict(offset=i,frame=r['frame'],transition=r['native']['transition_state'],
                palette=r['snes_palette']) for i,r in enumerate(native)]))
        tables.append(f'<h2>Room {room}</h2><p>First scenery pixel: NES +{visible[0]}, SNES +{visible[1]} frames.</p>'
            '<table><tr><th>Fade level</th><th>NES generation</th><th>SNES generation</th><th>PPU shadow</th><th>Prepared source</th><th>Prepared BG</th></tr>'+''.join(
                '<tr>'+''.join(f'<td>{v}</td>' for v in (s['level'],s['nes_generation_offset'],s['snes_generation_offset'],
                *s['delivery_offsets'].values()))+'</tr>' for s in steps)+'</table>')
    report=dict(observer_equivalent=True,rooms=rooms,
        sources={str(p):sha(p) for p in (reference/'capture.json',candidate/'capture.json',normal/'capture.json',rom,palette,labels,Path(__file__))},
        scope='Fixed forty-frame windows from rendering-enable, with four completed original fade generations identified by '
              'level and dirty flag. Exact NES indices trace shadow/cache and RGB555 words trace staged BG; no image realignment. '
              'A later generation with unchanged RGB555 words has no measurable new prepared-BG delivery and is explicitly marked ambiguous. '
              'The first nonblack fixed-band pixel separately measures visibility, not a CGRAM read. Full old timeline fields and PCM '
              'are identical to the normal-core control. No full-game or physical audio pass.')
    out.mkdir(parents=True,exist_ok=False)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Fade pipeline timing</title>'
        '<style>body{background:#101821;color:#eee;font:17px system-ui;margin:30px}td,th{padding:8px;border:1px solid #567}table{border-collapse:collapse}a{color:#9df}</style>'
        '<h1>Fade pipeline timing</h1><p>'+html.escape(report['scope'])+'</p><p><a href="report.json">Full snapshots and hashes</a></p>'+''.join(tables))
    print(json.dumps(dict(observer_equivalent=True,rooms=[dict(room=r['room'],steps=r['steps'],visible=r['first_nonblack_band_offsets']) for r in rooms]),indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('reference','candidate','normal','rom','palette','labels','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();audit(a.reference,a.candidate,a.normal,a.rom,a.palette,a.labels,a.out)
