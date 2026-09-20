"""Retain exact combat load costs and failures for the in-place shift trial."""
import argparse
from collections import Counter
import csv
import html
import json
from pathlib import Path
import shutil
import wave

from tools.audit_main_display_latency import bound_report
from tools.audit_park_instructions import parse
from tools.benchmark_report import sha, verify_capture
from tools.build_combat_outlier_review import outliers, context, excerpt_bounds
from tools.build_signed_shift_trial import ADDRESS, ORIGINAL, OPTIMIZED, patch
from tools.capture_combat_instructions import equivalent
from tools.combat_campaign import installed, verify_pair


def shift_cost(rows, first, last, image):
    costs=Counter(); calls=[]; pending=None
    for i in range(first,last):
        r=rows[i]; pc=r['pc']; low=pc&65535
        if not 0xc1 <= pc>>16 <= 0xc8:continue
        if ADDRESS <= low < ADDRESS+17:
            if image[pc&0x3fffff] != r['opcode']:
                raise ValueError('Shift trace opcode disagrees with cartridge')
            costs[pc]+=rows[i+1]['clock']-r['clock']
        block=image[(pc&0x3f0000)+ADDRESS:(pc&0x3f0000)+ADDRESS+17]
        branch=ADDRESS+(15 if block==ORIGINAL else 11)
        body_entry=(low==ADDRESS+2 and rows[i-1]['pc'] not in
                    ((pc&0xff0000)+ADDRESS,(pc&0xff0000)+branch))
        if low == ADDRESS or body_entry:
            if pending is not None:raise ValueError('Nested or unfinished shift block')
            pending=r
        elif low == ADDRESS+17 and pending is not None:
            if r['s'] != pending['s'] or pc>>16 != pending['pc']>>16:
                raise ValueError('Shift exit stack/bank differs')
            calls.append(dict(entry=pending, after=r, clocks=r['clock']-pending['clock']))
            pending=None
    if pending is not None or not calls:raise ValueError('Missing complete shift calls')
    return dict(calls=calls, own_instruction_clocks=sum(costs.values()),
        inclusive_clocks=sum(c['clocks'] for c in calls),
        mean_inclusive_clocks=sum(c['clocks'] for c in calls)/len(calls))


def audit(out):
    specs=(('parent-alley','build/receiver-dispatch-1916','build/dispatch-combat-1930',
            'build/combat-instruction-control-1941','build/combat-alley-instructions-1942',2560),
        ('parent-school','build/receiver-dispatch-1916','build/dispatch-combat-1930',
            'build/combat-instruction-control-1941','build/combat-school-instructions-1943',4177),
        ('trial-school','build/signed-shift-trial-1947','build/signed-shift-combat-1948',
            'build/signed-shift-instruction-control-1950','build/signed-shift-school-instructions-1952',4176))
    paths=[Path(__file__),Path('tools/capture_combat_instructions.py'),
        Path('tools/build_signed_shift_trial.py'),Path('tools/audit_park_instructions.py'),
        Path('tools/combat_campaign.py'),Path('tools/build_combat_outlier_review.py')]
    oracle=Path('build/signed-shift-oracle-1956/report.json')
    proof=bound_report(oracle)
    for p,d in proof['files'].items():
        if sha(oracle.parent/p)!=d:raise ValueError('Changed executed oracle artifact')
    if not proof['passed']:raise ValueError('Unqualified instruction replacement')
    parent=Path(specs[0][1]);candidate=Path(specs[2][1])
    if patch((parent/'native-cpu.sfc').read_bytes()) != (candidate/'native-cpu.sfc').read_bytes():
        raise ValueError('Different trial patch')
    paths.extend((oracle,parent/'native-cpu.sfc',candidate/'native-cpu.sfc'))
    out.mkdir(parents=True,exist_ok=False)
    runs={};cards=[]
    for name,rom,root,control,capture,frame in specs:
        rom,root,control,capture=map(Path,(rom,root,control,capture))
        binding=bound_report(capture/'instruction-control.json')
        bound_report(control/'instruction-control.json')
        _, result, normal_rows, normal=verify_pair(root,'running-jumps','snes',rom)
        with installed('running-jumps'):
            receipt,timeline=verify_capture(capture)
            base,plain=verify_capture(control)
        equivalent(receipt,timeline,base,plain)
        if timeline!=normal_rows or sha(control/'audio.wav')!=sha(normal/'audio.wav'):
            raise ValueError('Instruction core changed main-observer control')
        trace=Path(receipt['instruction_trace']['path'])
        if sha(trace)!=receipt['instruction_trace']['sha256']:raise ValueError('Changed trace')
        with trace.open() as f:rows=parse(csv.reader(f),binding['first'],binding['last'])
        loop=next(l for l in result['iterations'] if l['start']['frame']==frame)
        first=next(i for i,r in enumerate(rows) if r['clock']==loop['start']['clock'])
        last=next(i for i,r in enumerate(rows) if r['clock']==loop['finish']['clock'])
        if rows[first]['pc']!=loop['start']['pc'] or rows[last]['pc']!=loop['finish']['pc']:
            raise ValueError('Exact loop endpoints differ')
        image=(rom/'native-cpu.sfc').read_bytes()
        costs=Counter()
        for a,b in zip(rows[first:last],rows[first+1:last+1]):costs[f'{a["pc"]:06x}']+=b['clock']-a['clock']
        total=rows[last]['clock']-rows[first]['clock']
        if sum(costs.values())!=total:raise ValueError('Elapsed cost partition incomplete')
        calls=shift_cost(rows,first,last,image) if name.endswith('school') else None
        events=[context(x['loop'],timeline) for x in outliers(result['iterations'],timeline)]
        runs[name]=dict(loop=loop,strict_passed=result['passed'],outliers=events,
            elapsed_master_clocks=total,shift=calls,
            top_own_instruction_clocks=costs.most_common(30),observer_neutral=True)
        cards.append(f'<h2>{name}: frames {frame}–{loop["finish"]["frame"]}</h2><p>{total:,} elapsed master clocks. Strict cadence pass: {result["passed"]}.</p><div class="grid">')
        for f in (frame,frame+1,loop['finish']['frame'],loop['finish']['frame']+7):
            source=capture/f'frames/frame-{f:05d}.png';dest=f'{name}-{f}.png'
            if sha(source)!=timeline[f-1]['frame_image_sha256']:raise ValueError('Changed frame')
            shutil.copyfile(source,out/dest);paths.append(source)
            cards.append(f'<figure><img src="{dest}"><figcaption>Actual frame {f}</figcaption></figure>')
        cards.append('</div>')
        _,_,a,b=excerpt_bounds(timeline,frame,loop['finish']['frame'])
        audio=capture/'audio.wav'
        with wave.open(str(audio),'rb') as wav:
            params=wav.getparams();pcm=wav.readframes(wav.getnframes())
        block=params.nchannels*params.sampwidth;dest=f'{name}.wav'
        with wave.open(str(out/dest),'wb') as wav:
            wav.setparams(params);wav.writeframes(pcm[a*block:b*block])
        runs[name]['audio']=dict(file=dest,source=str(audio),first=a,last=b)
        cards.append(f'<audio controls preload="none" src="{dest}"></audio>')
        paths.extend((capture/'capture.json',capture/'instruction-control.json',control/'capture.json',
            control/'instruction-control.json',rom/'manifest.json',trace,audio,
            root/'running-jumps-snes-observed/combat-observer.json',
            root/'running-jumps-snes-normal/combat-observer.json'))
    entry=Path('build/signed-shift-entry-1953/report.json');visibility=json.loads(entry.read_text())
    paths.append(entry)
    report=dict(runs=runs,oracle_passed=proof['passed'],entry=visibility,
        release_ready=False,deployed=False,physical_speed_verified=False,pop_free_verified=False,
        sources={str(p):sha(p) for p in paths},
        scope='Exact trace endpoints of observed running-jump load loops. Same-core observers '
              'preserve complete RAM/video/input timelines and PCM. Own instruction times include '
              'events; inclusive call times may contain interrupts. Encounters can diverge. '
              'No cross-system equal-work speed or audio-fidelity verdict; strict failures retained.')
    page='''<!doctype html><meta charset="utf-8"><title>Signed shift load trial</title>
<style>body{font:17px system-ui;background:#101821;color:#eef;max-width:1200px;margin:30px auto}
a{color:#8df}.grid{display:grid;grid-template-columns:repeat(4,1fr)}img{width:100%;image-rendering:pixelated}figure{margin:8px}audio{width:100%}</style>
<h1>Signed shift: measured load optimization, not a release</h1>
<p>Return-to-school interval: 27 → 26 frames in this replay. Alley remains 15 frames.
The strict speed gate still fails. Full-route room-entry graphics REGRESS:
first scenery after enable is 8/6/7 frames versus NES 7/7/7; fixed-offset fades fail.
The 17-byte replacement passes 589,824 executed
operand/flag cases; three broken variants are rejected. No Rival deployment.</p>'''
    page+='<p>'+html.escape(report['scope'])+'</p>'+''.join(cards)
    page+='<p><a href="report.json">All costs and retained failures</a> · <a href="../signed-shift-entry-1953/">Full-route room-entry graphics</a></p>'
    (out/'index.html').write_text(page)
    report['artifacts']={p.name:sha(p) for p in out.iterdir()}
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:dict(clocks=v['elapsed_master_clocks'],shift=None if v['shift'] is None else
        {n:v['shift'][n] for n in ('own_instruction_clocks','inclusive_clocks','mean_inclusive_clocks')}) for k,v in runs.items()}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True)
    audit(**vars(p.parse_args()))
