"""Compare like-for-like game counters and physical load timing, preserving legacy failures.

The global SNES NMI counter and NES $010B are not interchangeable during
loading. A reference-matched load is still measured in full, never deducted.
"""
import argparse
import csv
from html import escape
import json
from pathlib import Path
import shutil

import numpy as np

from tools.audit_combat_loops import PHASES
from tools.audit_combat_room_entry import first_entry
from tools.audit_main_display_latency import bound_report
from tools.audit_room_entry import load_anchors, visibility_latencies
from tools.audit_scroll_publication import BACKGROUND_REGION, frame_path, rgb555
from tools.benchmark_report import sha, verify_capture
from tools.capture_combat_instructions import equivalent
from tools.combat_campaign import installed
from tools.review_candidate_combat import native_clip


def parse(records,system,points,image):
    events=[];active=None;loops=[];outside=[];pending=None
    for raw in records:
        if len(raw)!=(50 if system=='nes' else 56):raise ValueError('Wrong event width')
        frame,line,event=int(raw[0]),int(raw[1]),int(raw[3]);pc=int(raw[4],16)
        if event not in points or pc&65535!=points[event] or not 1<=frame or not -1<=line<262:
            raise ValueError('Wrong counter observation')
        offset=16+0x10000+pc if system=='nes' else pc&0x3fffff
        if system=='snes' and not 0xc1<=pc>>16<=0xc8:raise ValueError('Unexpected executing bank')
        wanted={0:b'\xa9\x00',1:bytes.fromhex('2031f7'),2:bytes.fromhex('ee2b05'),
                3:bytes.fromhex('8d0b01'),4:bytes.fromhex('a9c0')}[event]
        if system=='snes' and event==0:
            wanted=bytes.fromhex('a9018de11ca9008d0b01')
        if image[offset:offset+len(wanted)]!=wanted:raise ValueError('Observed opcode preimage differs')
        row=dict(frame=frame,line=line,event=event,pc=pc,game_tick=int(raw[6]),
            stack=int(raw[12 if system=='nes' else 13]),a=int(raw[9 if system=='nes' else 19]))
        if not 0<=row['game_tick']<=255 or (events and frame<events[-1]['frame']):raise ValueError('Invalid counter/frame')
        events.append(row)
        if event==3:
            if pending is not None or row['a']!=0:raise ValueError('Invalid reset entry')
            pending=row
        if event==4:
            if pending is None or row['stack']!=pending['stack'] or row['game_tick']!=0:
                raise ValueError('Reset did not clear game counter')
            pending=None
        if event==0:
            if active is not None:raise ValueError('Overlapping loops')
            active=dict(start=row,events=[row],input=None)
        elif active is not None:
            active['events'].append(row)
            if event==1:
                if active['input'] or row['game_tick'] or row['stack']!=active['start']['stack']:
                    raise ValueError('Input counter/stack not reset')
                active['input']=row
            if event==2:
                if active['input'] is None or row['stack']!=active['start']['stack']:
                    raise ValueError('Missing input or wrong completion stack')
                active.update(finish=row,frame_span=row['frame']-active['start']['frame'])
                loops.append(active);active=None
        else:outside.append(row)
    if pending is not None or not loops:raise ValueError('Incomplete counter coverage')
    return loops,dict(outside=outside,trailing=active)


def signature(loop):
    start=loop['start']['frame']
    return [dict(frame_offset=r['frame']-start,event=r['event'],game_tick=r['game_tick']) for r in loop['events']]


def compare_load(reference,trial):
    return dict(elapsed_frames_no_slower=trial['frame_span']<=reference['frame_span'],
        counter_sequence_exact=signature(reference)==signature(trial),
        same_final_game_tick=trial['finish']['game_tick']==reference['finish']['game_tick'])


def phase_gate(loops,rows,matched_load):
    result={}
    for phase in PHASES:
        chosen=[r for r in loops if rows[r['start']['frame']-1]['phase']==phase]
        frames=[r['frame'] for r in rows if r['phase']==phase]
        if not chosen or not frames:raise ValueError('Missing combat phase')
        errors=[]
        for loop in chosen:
            is_load=(loop['start']['frame'],loop['finish']['frame'])==matched_load
            if loop['finish']['game_tick']!=2 or (not is_load and loop['frame_span']!=2):
                errors.append(dict(start=loop['start']['frame'],span=loop['frame_span'],tick=loop['finish']['game_tick']))
        for a,b in zip(chosen,chosen[1:]):
            if b['start']['frame']!=a['finish']['frame']:
                errors.append(dict(missing_or_gapped_loop=a['finish']['frame'],next_start=b['start']['frame']))
        # Check completion coverage in elapsed frames instead of pretending
        # a measured loading iteration should contain hidden gameplay loops.
        if chosen[0]['start']['frame']>frames[0]+1 or chosen[-1]['finish']['frame']<frames[-1]-1:
            errors.append(dict(incomplete_phase=True))
        result[phase]=dict(loops=len(chosen),errors=errors,passed=not errors)
    return result


def audit(out):
    if out.exists():raise ValueError('Fresh output required')
    root=Path('build');sources={};data={};censored={};summaries={}
    specs=(('nes','load-counter-nes-2352','park-hold-nes-normal-2271'),
           ('snes','load-counter-snes-2353','compact-pair-combat-2243/running-jumps-snes-normal'))
    for system,observed,normal in specs:
        folder=root/observed;control=root/normal;binding=bound_report(folder/'counter-observer.json')
        context=installed('running-jumps')
        with context:
            receipt,rows=verify_capture(folder);base,plain=verify_capture(control)
        equivalent(receipt,rows,base,plain)
        image=(Path('roms/river-city-ransom-us.nes') if system=='nes' else root/'compact-pair-trial-2242/native-cpu.sfc').read_bytes()
        if not binding['observer_neutral']:raise ValueError('Non-neutral observer')
        sources.update(binding['sources']);sources[str(folder/'counter-observer.json')]=sha(folder/'counter-observer.json')
        for p in (control/'timeline.json',control/'audio.wav'):sources[str(p)]=sha(p)
        with Path(binding['trace']).open() as f:loops,censored[system]=parse(list(csv.reader(f)),system,{int(k):int(v,16) for k,v in binding['points'].items()},image)
        selected=next(l for l in loops if bytes.fromhex(rows[l['start']['frame']-1]['game_ram_hex'])[0x42]==0
            and bytes.fromhex(rows[l['finish']['frame']-1]['game_ram_hex'])[0x42]==1)
        if [r['event'] for r in selected['events']]!=[0,1,3,4,2]:raise ValueError('Different first alley-load path')
        entry=first_entry(rows,1);anchors=load_anchors(rows,entry)
        if not selected['start']['frame']<anchors['room_change_frame']<=anchors['enable_frame']<=selected['finish']['frame']:
            raise ValueError('First load and visibility edge differ')
        paths=[frame_path(folder,r) for r in rows[entry:entry+40]]
        x0,y0,x1,y1=BACKGROUND_REGION;pixels=[rgb555(p)[y0:y1,x0:x1] for p in paths]
        visible=next((i for i,p in enumerate(pixels) if np.any(p)),None)
        summaries[system]=dict(loop=selected,signature=signature(selected),anchors=anchors,
            visibility=visibility_latencies(anchors,visible),first_visible_offset=visible)
        data[system]=(folder,rows,loops,selected,paths,pixels)
        for p in paths:sources[str(p)]=sha(p)
    comparisons=compare_load(data['nes'][3],data['snes'][3])
    differences=[int(np.any(a!=b,axis=2).sum()) for a,b in zip(data['nes'][5],data['snes'][5])]
    comparisons.update(all40_backgrounds_exact=not any(differences),
        full_room_change_to_visible_no_slower=summaries['snes']['visibility']['room_change_to_visible']<=summaries['nes']['visibility']['room_change_to_visible'],
        full_rendering_off_to_visible_no_slower=summaries['snes']['visibility']['rendering_off_to_visible']<=summaries['nes']['visibility']['rendering_off_to_visible'])
    target=data['snes'][3];matched=(target['start']['frame'],target['finish']['frame'])
    phases=phase_gate(data['snes'][2],data['snes'][1],matched)
    legacy=bound_report(root/'compact-pair-combat-review-2249/report.json')
    old=next(e for e in legacy['outliers'] if (e['first'],e['last'])==matched)
    if old['nmi_advances']!=8 or old['frame_span']!=target['frame_span']:raise ValueError('Different retained legacy outlier')
    sources.update(legacy['sources']);sources[str(root/'compact-pair-combat-review-2249/report.json')]=sha(root/'compact-pair-combat-review-2249/report.json')
    import copy
    bad=copy.deepcopy(target);bad['frame_span']+=1
    late_rejected=not all(compare_load(data['nes'][3],bad).values())
    badloops=copy.deepcopy(data['snes'][2]);index=next(i for i,l in enumerate(badloops) if data['snes'][1][l['start']['frame']-1]['phase']=='combat_take_hits')+5
    badloops[index]['finish']['frame']+=1;badloops[index]['frame_span']+=1
    gameplay_rejected=not all(p['passed'] for p in phase_gate(badloops,data['snes'][1],matched).values())
    if not late_rejected or not gameplay_rejected:raise ValueError('Deadline mutant accepted')
    out.mkdir(parents=True);cards=[];clips=[]
    for system,(folder,rows,loops,loop,paths,pixels) in data.items():
        for offset in (0,7,11,15,19,39):shutil.copyfile(paths[offset],out/f'{system}-{offset}.png')
        a=max(1,loop['start']['frame']-30);b=min(len(rows),loop['finish']['frame']+40)
        clip=native_clip(folder/'audio.wav',out/f'{system}.wav',rows[a-1]['audio_start_sample'],rows[b-1]['audio_start_sample']+rows[b-1]['audio']['samples'])
        clips.append(clip)
    for offset in (0,7,11,15,19,39):cards.append(f'<h2>Rendering enable +{offset}</h2><div class="grid">'+''.join(f'<figure><img src="{s}-{offset}.png"><figcaption>{s}</figcaption></figure>' for s in ('nes','snes'))+'</div>')
    for name in (__file__,'tools/capture_load_counter.py','tools/audit_combat_room_entry.py','tools/audit_room_entry.py',
        'tools/audit_scroll_publication.py','tools/audit_combat_loops.py','tools/benchmark_report.py',
        'tools/capture_combat_instructions.py','tools/review_candidate_combat.py','tests/test_load_counter.py'):
        sources[str(Path(name))]=sha(Path(name))
    if any(sha(Path(p))!=v for p,v in sources.items()):raise ValueError('Sources changed during audit')
    result=dict(reference_context_passed=all(comparisons.values()) and all(p['passed'] for p in phases.values()),
        comparisons=comparisons,combat_phases=phases,summaries=summaries,censored=censored,
        legacy_strict_passed=legacy['passed'],legacy_nmi_counter_delta=old['nmi_advances'],
        game_counter_at_completion={s:v['loop']['finish']['game_tick'] for s,v in summaries.items()},
        mismatch_pixels=differences,late_load_mutation_rejected=late_rejected,late_gameplay_mutation_rejected=gameplay_rejected,
        equal_work_verified=False,physical_speed_verified=False,release_ready=False,clips=clips,sources=sources,
        scope=__doc__,counter_semantics='NES $010B and SNES $010B both reset during this loop and finish at2. '
          'SNES $1C04/05 instead advances8 across the whole interval. Physical elapsed frames are15 in both. '
          'Independent input/actor histories; not equal CPU workload or full-game certification.')
    page='<!doctype html><meta charset="utf-8"><title>Load timing: comparable counters</title><style>body{background:#101820;color:#eee;font:17px system-ui;max-width:1100px;margin:30px auto}a{color:#8df}.grid{display:flex}img{width:384px;image-rendering:pixelated}pre{white-space:pre-wrap}audio{width:100%}</style><h1>Alley load: NES and SNES both15 frames</h1><p>'+escape(result['counter_semantics'])+'</p><p>The old strict failure remains intact. A separate reference-context audit checks the entire load and all remaining combat loop deadlines.</p><pre>'+escape(json.dumps(comparisons,indent=2))+'</pre><a href="report.json">All counters, loops, gates and source hashes</a>'
    page+=''.join(f'<h2>{s} native load audio</h2><audio controls src="{s}.wav"></audio>' for s in ('nes','snes'))+''.join(cards)
    (out/'index.html').write_text(page);result['artifacts']={p.name:sha(p) for p in out.iterdir()}
    (out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('reference_context_passed','comparisons','combat_phases','legacy_strict_passed','game_counter_at_completion')}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True)
    audit(**vars(p.parse_args()))
