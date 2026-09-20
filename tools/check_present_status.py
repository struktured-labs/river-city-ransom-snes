"""Verify Present Status digits against original NES CIRAM and rendered pixels."""
import argparse
import html
import json
from pathlib import Path
import shutil
import struct

import numpy as np
from PIL import Image

try:
    from .benchmark_report import sha,verify_capture
except ImportError:
    from benchmark_report import sha,verify_capture

PHASES=('status_visible','status_reopen_visible')
GLYPHS=tuple(row*32+col for row in (5,7,9,11,13,15,17,19,21,22)
             for col in (13,14,28,29))
REGION=(8,32,248,208)
PATCHES=(0x6ba6f,0x6ba75,0x6ba7b)
STAT_ROWS=(5,7,9,11,13,15,17,19,21,22)


def state_digits(ram):
    # Original B9xx..BA27 number-print callers load $049F,X, $04A3,X,
    # ... $04C3,X with X=0/1. BA28 converts the resulting packed decimal
    # digits into F4..FD tiles, blanking leading zeroes (not the units).
    values=[ram[0x49f+stat*4+player] for stat in range(10) for player in (0,1)]
    tiles=[]
    for n in values:
        tiles.extend((0xf4+n//100 if n>=100 else 0,
                      0xf4+(n//10)%10 if n>=10 else 0,0xf4+n%10))
    return values,tiles


def check_state_values(folder,phase):
    values,expected=state_digits((folder/(phase+'.ram')).read_bytes())
    slots=[row*32+col for row in STAT_ROWS for col in (12,13,14,27,28,29)]
    shadow=(folder/(phase+'.nametable')).read_bytes()
    actual=[shadow[i] for i in slots]
    vram_file=folder/(phase+'.vram')
    published=None
    if vram_file.exists():
        vram=vram_file.read_bytes()
        published=[vram[(0x2000+i)*2] for i in slots]
    return dict(values=values,expected=expected,shadow=actual,vram=published,
                passed=expected==actual and (published is None or expected==published))


def patch_scope(old,new):
    a,b=old.read_bytes(),new.read_bytes()
    if len(a)!=0x200000 or len(b)!=len(a):
        raise ValueError('Expected original-sized native images')
    changed={i for i,(x,y) in enumerate(zip(a,b)) if x!=y}
    expected={start+i for start in PATCHES for i in range(3)}
    if changed-set(range(0xffdc,0xffe0))!=expected:
        raise ValueError('Changes outside three Present Status instructions')
    for data in (a,b):
        complement,checksum=struct.unpack_from('<HH',data,0xffdc)
        if complement^checksum!=65535 or sum(data)&65535!=checksum:
            raise ValueError('Invalid native checksum')
    for offset,operand in zip(PATCHES,(0x2006,0x2006,0x2007)):
        if a[offset:offset+3]!=b'\x8d'+struct.pack('<H',operand) or b[offset]!=0x20:
            raise ValueError('Unexpected number-printer preimage or replacement')
    return sorted(changed)


def glyphs(folder,phase,vram=False):
    data=(folder/(phase+('.vram' if vram else '.nametable'))).read_bytes()
    return [data[(0x2000+i)*2 if vram else i] for i in GLYPHS]


def pixels(folder,phase):
    x0,y0,x1,y1=REGION
    return np.asarray(Image.open(folder/(phase+'.png')).convert('RGB'))[y0:y1,x0:x1]>>3


def compare(reference,candidate,phases=PHASES):
    result=[]
    for phase in phases:
        original=glyphs(reference,phase)
        shadow=glyphs(candidate,phase)
        vram=glyphs(candidate,phase,True)
        if not all(original):
            raise ValueError('Original status fields are blank or scenario missed the status screen')
        mismatch=int(np.any(pixels(reference,phase)!=pixels(candidate,phase),axis=2).sum())
        state=check_state_values(candidate,phase)
        result.append(dict(phase=phase,original=original,shadow=shadow,vram=vram,state_values=state,
                           mismatch_pixels=mismatch,
                           passed=original==shadow==vram and mismatch==0 and state['passed']))
    return result


def build(reference,previous,candidate,old_rom,new_rom,out,park_before=None,park_after=None,
          combat_reference=None,combat_candidate=None):
    receipts={}
    for label,folder,system in (('nes',reference,'nes'),('previous',previous,'snes'),('snes',candidate,'snes')):
        r,rows=verify_capture(folder)
        if (r['system']!=system or not r['capture_complete'] or r['scenario_name']!='pause-status'
                or any(x['input_requested']!=x['input_delivered'] or x['fault'] for x in rows)):
            raise ValueError('Invalid input-only status capture')
        receipts[label]=r
    if len({r['scenario_sha256'] for r in receipts.values()})!=1:
        raise ValueError('Status input scenarios differ')
    if any(r['templates']['menu']['source_rom']!=receipts['nes']['rom_sha256'] for r in receipts.values()):
        raise ValueError('Original NES reference mismatch')
    if receipts['previous']['rom_sha256']!=sha(old_rom) or receipts['snes']['rom_sha256']!=sha(new_rom):
        raise ValueError('Capture is not bound to compared ROM')
    changed=patch_scope(old_rom,new_rom)
    result=compare(reference,candidate)
    negative=compare(reference,previous)
    gates=dict(all_40_digits_and_status_pixels_exact=all(x['passed'] for x in result),
               old_blank_fields_reproduced=all(x['shadow']==[0]*40 and not x['passed'] for x in negative),
               only_three_mmio_instructions_changed=len(changed)==13)
    report=dict(schema='rcr-present-status-audit-v1',passed=all(gates.values()),gates=gates,
                result=result,negative_control=negative,changed_rom_offsets=changed,
                captures={label:dict(path=str(folder),capture_sha256=sha(folder/'capture.json'),
                                     rom_sha256=receipts[label]['rom_sha256'])
                          for label,folder in (('nes',reference),('previous',previous),('snes',candidate))},
                scope='Initial and repeated status entry: 40 digits, original CIRAM, SNES shadow/VRAM and complete status-region pixels. Not whole-game speed certification.')
    if bool(park_before)!=bool(park_after) or bool(combat_reference)!=bool(combat_candidate):
        raise ValueError('Supplementary captures must be paired')
    if park_before:
        for folder,rom in ((park_before,old_rom),(park_after,new_rom)):
            r,_=verify_capture(folder)
            if r['rom_sha256']!=sha(rom) or not r['capture_complete'] or r['scenario_name']!='traversal-park-stress':
                raise ValueError('Unbound or incomplete park regression capture')
        report['park_equality']={name:sha(park_before/name)==sha(park_after/name)
                                 for name in ('timeline.json','audio.wav')}
        gates['complete_park_timeline_and_pcm_unchanged']=all(report['park_equality'].values())
        report['park_capture_hashes']=[sha(p/'capture.json') for p in (park_before,park_after)]
    if combat_reference:
        combat=[]
        for folder,system,rom_hash in ((combat_reference,'nes',receipts['nes']['rom_sha256']),
                                      (combat_candidate,'snes',sha(new_rom))):
            r,_=verify_capture(folder)
            if (r['system']!=system or r['rom_sha256']!=rom_hash or not r['capture_complete']
                    or r['scenario_name']!='pause-status-after-combat'):
                raise ValueError('Unbound post-encounter status capture')
            combat.append(dict(system=system,capture_sha256=sha(folder/'capture.json'),
                initial=check_state_values(folder,'status_visible'),
                after=check_state_values(folder,'status_visible_after_combat')))
        report['post_encounter']=combat
        report['post_encounter_scope']='Independent encounters: each displayed value must match its own game RAM; not forced matching health or proof of identical combat speed.'
        gates['post_encounter_digits_match_own_game_ram']=all(c['initial']['passed'] and c['after']['passed'] for c in combat)
    report['passed']=all(gates.values())
    out.mkdir(parents=True,exist_ok=False)
    cards=[]
    for phase in PHASES:
        cards.append('<h2>'+html.escape(phase)+'</h2>')
        for label,folder in (('nes',reference),('previous',previous),('snes',candidate)):
            name=label+'-'+phase+'.png'
            shutil.copyfile(folder/(phase+'.png'),out/name)
            cards.append(f'<figure><figcaption>{label}</figcaption><img src="{name}"></figure>')
    if combat_reference:
        cards.append('<h2>After independent encounters</h2><p>Health may differ; each number is checked against that game\'s own RAM.</p>')
        for label,folder in (('nes',combat_reference),('snes',combat_candidate)):
            name=label+'-after-encounter.png'
            shutil.copyfile(folder/'status_visible_after_combat.png',out/name)
            cards.append(f'<figure><figcaption>{label}</figcaption><img src="{name}"></figure>')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    (out/'index.html').write_text('''<!doctype html><meta charset="utf-8"><title>Present Status regression</title>
<style>body{background:#101924;color:#eee;font:16px system-ui;padding:24px}figure{display:inline-block;margin:8px}img{width:384px;image-rendering:pixelated}a{color:#9df}</style>
<h1>Present Status · original / missing stats / corrected</h1>
<p>All forty numeric tiles and the complete status-region pixels are checked on initial and repeated entry.
Only three original PPU-register instructions and the native checksum change.</p>
<a href="report.json">Source hashes and gates</a>'''+''.join(cards))
    print(json.dumps(dict(passed=report['passed'],gates=gates),indent=2))
    return report['passed']


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('reference','previous','candidate','old-rom','new-rom','out'):
        p.add_argument('--'+name,type=Path,required=True)
    for name in ('park-before','park-after','combat-reference','combat-candidate'):
        p.add_argument('--'+name,type=Path)
    a=p.parse_args()
    raise SystemExit(0 if build(a.reference,a.previous,a.candidate,a.old_rom,a.new_rom,a.out,
                               a.park_before,a.park_after,a.combat_reference,a.combat_candidate) else 1)
