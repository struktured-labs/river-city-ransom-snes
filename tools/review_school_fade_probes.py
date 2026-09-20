"""Retain school-fade timing, every tested cap, and rejected early-work trials."""
import argparse
import csv
import html
import json
from pathlib import Path
import shutil

import numpy as np

from tools.audit_main_display_latency import bound_report
from tools.audit_park_instructions import parse
from tools.audit_room_load_profile import main_call_sections
from tools.audit_shift_fade_schedule import marks
from tools.audit_alley_entry_work import return_index,prepare_phases
from tools.audit_school_return import first_return
from tools.audit_scroll_publication import BACKGROUND_REGION,rgb555
from tools.benchmark_report import sha,verify_capture
from tools.capture_school_instructions import equivalent
from tools.review_combat_checkpoints import load,transition
from tools.school_return_campaign import installed


def timing():
    capture=Path('build/school-fade-instructions-2145');normal=Path('build/school-instruction-control-2144')
    rom=Path('build/saturating-shift-trial-2087')
    binding=bound_report(capture/'instruction-control.json');bound_report(normal/'instruction-control.json')
    with installed():
        receipt,timeline=verify_capture(capture);baseline,plain=verify_capture(normal)
    equivalent(receipt,timeline,baseline,plain)
    trace=Path(receipt['instruction_trace']['path'])
    if sha(trace)!=receipt['instruction_trace']['sha256'] or sha(rom/'native-cpu.sfc')!=receipt['rom_sha256']:
        raise ValueError('Changed instruction trace or cartridge')
    with trace.open() as stream:rows=parse(csv.reader(stream),binding['first'],binding['last'])
    index,_=first_return(timeline);enable=timeline[index]['frame']
    labels=lambda name:{r.split()[2].lstrip('.'):int(r.split()[1],16) for r in (rom/name).read_text().splitlines()}
    boot=labels('native_boot.lbl');runtime=labels('native_runtime.lbl');image=(rom/'native-cpu.sfc').read_bytes()
    nmis={r['clock']:r['pc'] for r in rows if r['pc'] in (boot['nmi'],0xc00000+boot['nmi'])}
    starts=[i for i,r in enumerate(rows) if r['pc']==0xc7f293 and r['frame']>=enable]
    if len(starts)<3:raise ValueError('Missing first three post-return iterations')
    calls=[]
    for i in starts[:3]:
        start=rows[i];fade=next(r for r in rows[i:] if r['pc']==0xc7e343 and r['s']==start['s']-2)
        parts=main_call_sections(rows[i:],start['frame'],fade,nmis)
        for c in parts:
            at=int(c['caller'],16)&0x3fffff
            if image[at]!=0x20 or int.from_bytes(image[at+1:at+3],'little')!=int(c['callee'],16)&65535:
                raise ValueError('Changed original main call')
        calls.append(dict(start=start,fade=fade,calls=parts,start_offset=start['frame']-enable,
                          fade_offset=fade['frame']-enable))
    producers=[]
    for i,r in enumerate(rows):
        if r['pc']==0xc00000+boot['native_prepare'] and enable<=r['frame']<enable+6:
            end=return_index(rows,i,0x60)
            producers.append(dict(entry=r,after=rows[end],phases=prepare_phases(rows,i,end,boot)))
    sources=dict(binding['sources'])
    for p in (capture/'instruction-control.json',normal/'instruction-control.json',capture/'capture.json',
              normal/'capture.json',rom/'native_boot.lbl',rom/'native_runtime.lbl'):
        sources[str(p)]=sha(p)
    return dict(enable_frame=enable,iterations=calls,producers=producers,
                marks=marks(rows,enable,runtime['gameplay_iteration_start']),observer_neutral=True),sources


def build(out):
    if out.exists():raise ValueError('Fresh review required')
    work,sources=timing();out.mkdir(parents=True)
    caps={'school':{8:2151,9:2162,10:2163,11:2164,12:2152,13:2165,14:2153,15:2166,16:2133},
          'alley':{8:2154,9:2167,10:2168,11:2169,12:2155,13:2170,14:2156,15:2171,16:2136}}
    x0,y0,x1,y1=BACKGROUND_REGION;results={};cards=[]
    for location,variants in caps.items():
        data=[];pictures={};baseline=None
        for cap,num in sorted(variants.items(),reverse=True):
            stem='both' if cap==16 else f'cap{cap}'
            root=Path('build')/f'{location}-{stem}-resume-{num}'
            report,rows=load(root)
            if baseline is None:baseline=(report,rows,(root/'initial.ram').read_bytes())
            if ((root/'initial.ram').read_bytes()!=baseline[2] or report['initial_registers']!=baseline[0]['initial_registers']
                    or [r['input_requested'] for r in rows]!=[r['input_requested'] for r in baseline[1]]):
                raise ValueError('Unequal checkpoint state or inputs')
            d=transition(rows);index=d['enable_index']
            pixels=[rgb555(root/r['frame_image'])[y0:y1,x0:x1] for r in rows[index:index+40]]
            visible=next((i for i,p in enumerate(pixels) if np.any(p)),None)
            d.update(idle_cap=cap,active_cap=cap-1,first_nonblack_offset=visible,
                change_to_visible=None if visible is None else d['enable_frame']+visible-d['change_frame'],
                brightness=[float(p.mean()) for p in pixels],source=str(root))
            data.append(d);pictures[cap]=[]
            for offset in (7,9):
                source=root/rows[index+offset]['frame_image'];dest=f'{location}-cap{cap}-offset{offset}.png'
                shutil.copyfile(source,out/dest);pictures[cap].append(dest)
            audio=f'{location}-cap{cap}.wav';shutil.copyfile(root/'audio.wav',out/audio)
            sources.update(report['sources'])
            for p in (root/'report.json',root/'timeline.json',root/'initial.ram',root/'audio.wav'):
                sources[str(p)]=sha(p)
        results[location]=data
        cards.append(f'<h2>{location}: every tested cap, same initial state</h2><table><tr><th>Idle/active cap</th><th>On→visible</th><th>Room→visible</th><th>Enable+7</th><th>Enable+9</th><th>Native audio</th></tr>')
        for d in sorted(data,key=lambda d:d['idle_cap']):
            cap=d['idle_cap']
            cards.append(f'<tr><td>{cap}/{cap-1}</td><td>{d["first_nonblack_offset"]}</td><td>{d["change_to_visible"]}</td>'+''.join(f'<td><img src="{f}"></td>' for f in pictures[cap])+f'<td><audio controls preload="none" src="{location}-cap{cap}.wav"></audio></td></tr>')
        cards.append('</table>')
    edges=[]
    for count,candidate,audit,oracle in [(1,'render-edge-trial-2172','render-edge-school-audit-2174','render-edge-oracle-2179'),
                                       (2,'render-edge2-trial-2177','render-edge2-school-audit-2180','render-edge2-oracle-2181')]:
        root=Path('build')/audit;d=bound_report(root/'report.json');proofroot=Path('build')/oracle
        proof=bound_report(proofroot/'report.json')
        if not proof['passed']:raise ValueError('Failed helper ABI oracle')
        for p,h in proof['artifacts'].items():
            if sha(proofroot/p)!=h:raise ValueError('Changed executed oracle')
        candidate=Path('build')/candidate
        if proof['sources'].get(str(candidate/'native-cpu.sfc'))!=sha(candidate/'native-cpu.sfc'):
            raise ValueError('Oracle binds different helper cartridge')
        edges.append(dict(passes=count,gates=d['gates'],samples=d['samples'],passed=d['passed'],oracle=proof['cases']))
        sources.update(d['sources']);sources.update(proof['sources'])
        for p in (root/'report.json',proofroot/'report.json'):sources[str(p)]=sha(p)
        cards.append(f'<h2>{count} synchronous edge pass(es): {"PASS" if d["passed"] else "FAIL"}</h2><p>Actual NES comparison retained; {proof["cases"]} dispatch/ABI cases pass, not full interrupt/VRAM qualification.</p><div class="grid">')
        for side in ('nes','snes'):
            source=root/f'{side}-07.png';dest=f'edge{count}-{side}-07.png';shutil.copyfile(source,out/dest)
            cards.append(f'<figure><img src="{dest}"><figcaption>{side}, enable+7</figcaption></figure>')
        cards.append('</div>')
    route=Path('build/render-edge-route-2175');receipt,_=verify_capture(route)
    if receipt['capture_complete']:raise ValueError('Expected retained incomplete forward route')
    sources[str(route/'capture.json')]=sha(route/'capture.json')
    for p in map(Path,(__file__,'tools/audit_park_instructions.py','tools/audit_room_load_profile.py',
        'tools/audit_shift_fade_schedule.py','tools/audit_alley_entry_work.py','tools/audit_school_return.py',
        'tools/review_combat_checkpoints.py','tools/capture_school_instructions.py')):
        sources[str(p)]=sha(p)
    report=dict(timing=work,caps=results,edge_trials=edges,sources=sources,deployed=False,release_ready=False,
        one_pass_route=dict(complete=False,frames=receipt['frames'],last_phase=receipt['segments'][-1]),
        scope='All rejected experiments retained. Cap pairs8/7..16/15 use identical restored state/input; '
        'school reference deadline is7 frames. Separate edge-pass trials are uninterrupted independent '
        'encounters, not same-state causal comparisons. Elapsed instruction clocks include DMA/interrupts. '
        'ABI fixtures use a clobbering bridge stub, not real VRAM. No timing threshold changed, '
        'fade timer modified, Rival deployment, physical-speed or acoustic claim.')
    page='<!doctype html><meta charset="utf-8"><title>School fade scheduling probes</title><style>body{background:#101820;color:#eef;font:16px system-ui;max-width:1400px;margin:30px auto}a{color:#8df}td,th{border:1px solid #567;padding:6px}td img{width:240px;image-rendering:pixelated}.grid{display:flex}.grid img{width:384px}audio{width:230px}pre{white-space:pre-wrap}</style>'
    page+='<h1>School fade: smaller budgets and earlier preparation are insufficient</h1><p>'+html.escape(report['scope'])+'</p><p><a href="report.json">All costs, outcomes and hashes</a></p>'
    page+='<p>First three original fade services occur at enable+3/+5/+7. In the first actor-update call,436,168 of651,750 elapsed clocks are ordinary NMI spans. Heavy hidden-row passes cost about108–113k clocks. Those diagnostic subtractions do not reduce acceptance timings.</p>'
    page+='<p>Every cap tested misses the school+7 target. Both early-work variants reach+8. The one-pass full route also times out at park west sweep; no complete forward-entry verdict is claimed. Two-pass full-route testing has not been run.</p>'+''.join(cards)
    (out/'index.html').write_text(page)
    report['artifacts']={p.name:sha(p) for p in out.iterdir()}
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),cap_cases=sum(len(v) for v in results.values()),edge_trials=len(edges),deployed=False)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True)
    build(**vars(p.parse_args()))
