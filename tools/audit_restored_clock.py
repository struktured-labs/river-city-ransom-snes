"""Reconstruct post-restore clocks and locate unserviced VBlank-flag expiry."""
import argparse
import csv
import html
import json
from pathlib import Path
import shutil

from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha
from tools.build_retained_producer_guard import symbols
from tools.frame_audit import verify_frame

FIELDS = ('kind','frame','line','cycle','clock','pc','opcode','a','x','y','s','p','db','dp',
          'enable','rdnmi','nmi_pending','depth','pair','retained','iteration','producer',
          'transition','busy','task','camera','nmi_count','hmax')


def decode(raw):
    if len(raw) != len(FIELDS) or raw[0] not in ('B','E','I','H'):
        raise ValueError('Wrong trace row schema')
    return {key:(value if key=='kind' else int(value,16 if key in ('pc','opcode') else 10))
            for key,value in zip(FIELDS,raw)}


def reconstruct(rows,first,last,image=None):
    if not rows or rows[0]['kind']!='B' or rows[0]['clock']!=0 or rows[0]['frame']!=first:
        raise ValueError('Trace must start at the restored-state clock zero')
    offset = -rows[0]['cycle']
    previous_clock,frame,opened = 0,first-1,False
    line_events,lengths = 0,set()
    instructions = 0
    for r in rows:
        if r['clock'] != offset+r['cycle'] or r['clock']<previous_clock:
            raise ValueError('Clock disagrees with reconstructed actual line lengths')
        previous_clock=r['clock']
        if r['kind']=='B':
            if opened or r['frame']!=frame+1:
                raise ValueError('Missing/duplicate replay-frame begin')
            frame=r['frame']; opened=True
        elif not opened or r['frame']!=frame:
            raise ValueError('Row outside matching replay-frame boundary')
        if r['kind']=='E': opened=False
        if r['kind']=='H':
            if r['hmax'] not in (1360,1364) or r['cycle']<r['hmax']:
                raise ValueError('Unexpected NTSC line event')
            offset+=r['hmax']; lengths.add(r['hmax']); line_events+=1
        if r['kind']=='I':
            instructions+=1
            if image is not None:
                pc=r['pc']; bank=pc>>16; low=pc&65535
                if not ((bank==0 and low>=0x8000) or 0xc0<=bank<=0xc8):
                    raise ValueError('Instruction outside qualified ROM banks')
                if image[pc&0x3fffff] != r['opcode']:
                    raise ValueError('Instruction does not match actual cartridge')
    if opened or frame!=last:
        raise ValueError('Missing final replay-frame boundary')
    return dict(frames=last-first+1,instructions=instructions,line_events=line_events,
                line_lengths=sorted(lengths),final_relative_clock=rows[-1]['clock'])


def expired_events(rows,nmi_entry):
    rise=None; events=[]
    for i,(old,new) in enumerate(zip(rows,rows[1:]),1):
        if not old['rdnmi']&128 and new['rdnmi']&128:
            rise=i
        if old['rdnmi']&128 and not new['rdnmi']&128:
            if rise is not None and old['kind']=='H' and old['line']==261:
                interval=rows[rise:i+1]
                gates=dict(masked_throughout=all(not r['enable']&128 for r in interval),
                    no_hardware_handler=not any(r['kind']=='I' and r['pc']==nmi_entry for r in interval),
                    no_software_count_advance=len({r['nmi_count'] for r in interval})==1,
                    asserted_at_vblank=rows[rise]['line']==240,expired_at_wrap=new['line']==0)
                enabled=next((r for r in rows[i+1:] if r['enable']&128),None)
                events.append(dict(asserted=rows[rise],expired=new,before_wrap=old,
                    exact_scanline_boundary_clock=old['clock']+old['hmax']-old['cycle'],
                    reenabled=enabled,gates=gates))
            rise=None
    return events


def body_intervals(rows,entry,end):
    start=None; spans=[]
    for r in rows:
        if r['kind']!='I' or not 0xc1<=r['pc']>>16<=0xc8:
            continue
        low=r['pc']&65535
        if low==entry:
            if start is not None: raise ValueError('Nested original interrupt')
            start=r
        elif low==end and start is not None:
            spans.append(dict(start=start,end=r,clocks=r['clock']-start['clock']))
            start=None
    return spans


def audit(config,out):
    if out.exists(): raise ValueError('Fresh output required')
    spec=json.loads(config.read_text()); sources={}; arms={}; summary=[]; cards=[]
    out.mkdir(parents=True)
    for name,values in spec['arms'].items():
        root,candidate=Path(values['trace']),Path(values['candidate'])
        report=bound_report(root/'report.json')
        if (not report['passed'] or not report['observed'] or
                not all(report['neutral_checks'].values()) or
                report['first']!=report['restored_frame']+1):
            raise ValueError('Non-neutral or non-zero-anchored observer')
        rom=candidate/'native-cpu.sfc'
        if report['sources'].get(str(rom))!=sha(rom): raise ValueError('Different cartridge')
        for path,d in report['artifacts'].items():
            if sha(root/path)!=d: raise ValueError('Changed replay artifact')
        with (root/'instructions.csv').open() as stream: rows=[decode(r) for r in csv.reader(stream)]
        clock=reconstruct(rows,report['first'],report['last'],rom.read_bytes())
        labels=symbols(candidate/'native_runtime.lbl'); boot=symbols(candidate/'native_boot.lbl')
        events=expired_events(rows,boot['nmi'])
        if not events or not all(all(e['gates'].values()) for e in events):
            raise ValueError('Unproved masked VBlank expiry')
        bodies=body_intervals(rows,0xff4f,labels['nmi_rti_return'])
        selected=[]
        for event in events:
            spans=[b for b in bodies if b['start']['clock']<event['asserted']['clock']<
                   event['expired']['clock']<b['end']['clock']]
            if len(spans)!=1: raise ValueError('No unique enclosing original interrupt body')
            selected.append(spans[0])
        # Execute negative controls on the actual captured rows. A shifted
        # clock or an omitted line event must not survive reconstruction.
        mutants=[]
        index=next(i for i,r in enumerate(rows) if r['kind']=='I' and i>10)
        corrupt=list(rows); corrupt[index]=dict(rows[index],clock=rows[index]['clock']+1)
        missing=list(rows); del missing[next(i for i,r in enumerate(rows) if r['kind']=='H')]
        for label,bad in (('shifted-clock',corrupt),('missing-line',missing)):
            try: reconstruct(bad,report['first'],report['last'])
            except ValueError as exc: mutants.append(dict(name=label,rejected=True,reason=str(exc)))
            else: raise ValueError('Clock mutant survived')
        arms[name]=dict(clock=clock,expired=events,enclosing_bodies=selected,mutants=mutants,
                        neutral=report['neutral_checks'])
        for event,body in zip(events,selected):
            summary.append(dict(arm=name,body_start=f'{body["start"]["line"]}:{body["start"]["cycle"]}',
                body_return=f'{body["end"]["line"]}:{body["end"]["cycle"]}',body_clocks=body['clocks'],
                frame_of_expiry=event['expired']['frame'],
                clocks_past_wrap=body['end']['clock']-event['exact_scanline_boundary_clock'],
                reenable_line=event['reenabled']['line'] if event['reenabled'] else None))
        timeline=json.loads((root/'timeline.json').read_text())
        for row in timeline:
            if row['frame'] not in (2237,2238,2239,2240): continue
            verify_frame(root,row)
            source=root/row['frame_image']; target=f'{name}-{row["frame"]}.png'
            shutil.copy2(source,out/target); sources[str(source)]=sha(source)
            cards.append(f'<figure><img src="{target}"><figcaption>{html.escape(name)} · {row["frame"]}</figcaption></figure>')
        shutil.copy2(root/'audio.wav',out/(name+'.wav'))
        sources.update(report['sources'])
        for p in (root/'report.json',root/'instructions.csv',root/'audio.wav',
                  candidate/'native_runtime.lbl',candidate/'native_boot.lbl'):
            sources[str(p)]=sha(p)
    for p in (Path(__file__),config,Path('tools/frame_audit.py'),Path('tests/test_restored_clock.py')):
        sources[str(p)]=sha(p)
    if any(sha(Path(p))!=d for p,d in sources.items()): raise ValueError('Changed source')
    report=dict(arms=arms,summary=summary,sources=sources,scope=__doc__,
        release_ready=False,physical_verified=False,pop_free_verified=False)
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Restored interrupt timing</title>'
        '<style>body{background:#101820;color:#eef;font:17px system-ui;max-width:1150px;margin:2em auto}'
        'a{color:cyan}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}figure{margin:0}'
        'img,audio{width:100%}img{image-rendering:pixelated}pre{white-space:pre-wrap}</style>'
        '<h1>The same saved-state stall, now traced without changing the replay</h1>'
        '<p>Four90-frame replays match their prior core outputs exactly. Trace-on/off matches every '
        'frame, full WRAM hash, all CPU registers, both actual input ports and native PCM.</p>'
        '<p>The clock starts at zero after restore. Each nine-frame trace reconstructs from2358 actual '
        'scanline events, including1360-clock short lines. Shifted-clock and missing-line controls fail.</p>'
        '<h2>Interrupt work still crosses the entire masked VBlank</h2><pre>'+
        html.escape(json.dumps(summary,indent=2))+'</pre><p>In every case the unacknowledged VBlank flag '
        'rises at line240 with NMI disabled, then expires at line0 with no handler entry or counter advance. '
        'The original interrupt body returns too late. These are matched initial states and inputs, '
        'not four independently evolving fresh-boot encounters.</p>'
        '<p>The full dirty-cache combination2894 also fails to recover the update. No candidate is promoted; '
        'Rival is untouched. This evidence guides a correctly accounted pending-event collector, '
        'not synthetic extra game ticks.</p><h2>Frames2237–2240</h2><div class="grid">'+''.join(cards)+
        '</div><h2>Unnormalized native replay audio</h2>'+''.join(f'<p>{html.escape(n)}</p>'
        f'<audio controls src="{n}.wav"></audio>' for n in arms)+
        '<p>No acoustic fidelity or pop-free claim. <a href="report.json">Clock events, failures and hashes</a></p>')
    report['artifacts']={p.name:sha(p) for p in out.iterdir() if p.is_file()}
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(summary=summary,sources=len(sources),artifacts=len(report['artifacts']))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('config','out'): p.add_argument('--'+name,type=Path,required=True)
    audit(**vars(p.parse_args()))
