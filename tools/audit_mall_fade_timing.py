"""Compare original mall fade scheduling and separately measure native sound waits."""
import argparse
from collections import Counter
import csv
import html
import json
from pathlib import Path

from tools.audit_alley_fade_schedule import POINTS, nes_iterations, neutral
from tools.audit_alley_entry_work import return_index, prepare_phases
from tools.audit_park_instructions import parse
from tools.audit_room_entry import entries
from tools.audit_room_load_profile import main_call_sections
from tools.benchmark_report import sha
from tools.nes_event_trace import validate


def audio_sections(rows,start,end,labels):
    """Strict nested sender/wait accounting; do not double-count nested time."""
    senders=[i for i in range(start,end) if rows[i]['pc']==0xc00000+labels['spc_frame']]
    if len(senders)>1:raise ValueError('Multiple packets in one bridge')
    bridge=rows[end]['clock']-rows[start]['clock']
    if not senders:return dict(bridge_clocks=bridge,packet=False)
    at=senders[0];after=return_index(rows,at,0x60)
    if after>end:raise ValueError('Sender crosses bridge return')
    waits=[]
    for i in range(at,after):
        if rows[i]['pc']!=0xc00000+labels['wait_port0']:continue
        done=return_index(rows,i,0x60)
        if done>after:raise ValueError('Wait crosses sender return')
        waits.append(dict(token=rows[i]['a']&255,entry=rows[i],after=rows[done],
            clocks=rows[done]['clock']-rows[i]['clock']))
    if [w['token'] for w in waits]!=[0x7d,0xd7,*range(0,23,2)]:
        raise ValueError('Incomplete paired sender handshake')
    sender=rows[after]['clock']-rows[at]['clock']
    wait=sum(w['clocks'] for w in waits)
    if sender<wait or bridge<sender:raise ValueError('Overlapping audio accounting')
    return dict(packet=True,bridge_clocks=bridge,sender_clocks=sender,wait_clocks=wait,
        bridge_outside_sender=bridge-sender,sender_outside_waits=sender-wait,waits=waits)


def audit(out):
    systems={};paths=[Path(__file__)]+[Path('tools')/n for n in (
        'audit_alley_fade_schedule.py','audit_alley_entry_work.py','audit_park_instructions.py',
        'audit_room_entry.py','audit_room_load_profile.py','benchmark_report.py','nes_event_trace.py',
        'snes9x_instruction_trace.inc','fceumm_queue_trace.inc')]
    specs=(('NES','mall-nes-events-1427','park-single-nes-331',None),
        ('Older783','mall-old-instructions-1428','main-phase-128-normal-784','main-phase-128-branded-783'),
        ('Current','mall-current-instructions-1425','postpublish-normal-1322','postpublish-keyon-1321'),
        ('Cutoff128','mall-cut128-instructions-1426','hidden-deadline128-normal-1407','hidden-deadline128-1405'))
    for name,capture,normal,candidate in specs:
        root=Path('build')/capture;base=Path('build')/normal
        receipt,timeline=neutral(root,base);index=entries(timeline)[2];enable=timeline[index]['frame']
        rom=Path('roms/river-city-ransom-us.nes') if candidate is None else Path('build')/candidate/'native-cpu.sfc'
        if sha(rom)!=receipt['rom_sha256']:raise ValueError('Wrong captured cartridge')
        paths.extend((root/'capture.json',base/'capture.json',rom))
        if candidate is None:
            binding=receipt['nes_event_trace'];trace=Path(binding['path'])
            if sha(trace)!=binding['sha256'] or binding['points']!=POINTS:raise ValueError('Wrong NES events')
            with trace.open() as f:events=list(csv.reader(f))
            validate(events,binding['first'],binding['last'],receipt['frames'],POINTS)
            iterations=nes_iterations(events,enable,4);audio=[];producers=[]
        else:
            binding=receipt['instruction_trace'];trace=Path(binding['path'])
            if sha(trace)!=binding['sha256']:raise ValueError('Changed instructions')
            with trace.open() as f:rows=parse(csv.reader(f),binding['first'],binding['last'])
            label_path=rom.parent/'native_boot.lbl';paths.append(label_path)
            labels={r.split()[2].lstrip('.'):int(r.split()[1],16) for r in label_path.read_text().splitlines()}
            nmi=labels['nmi'];nmis={r['clock']:r['pc'] for r in rows if r['pc'] in (nmi,0xc00000+nmi)}
            starts=[i for i,r in enumerate(rows) if r['pc']==0xc7f293 and r['frame']>=enable]
            if len(starts)<4:raise ValueError('Missing four main iterations')
            iterations=[];image=rom.read_bytes()
            for i in starts[:4]:
                fade=next(r for r in rows[i:] if r['pc']==0xc7e343 and r['s']==rows[i]['s']-2)
                calls=main_call_sections(rows[i:],rows[i]['frame'],fade,nmis)
                for call in calls:
                    pc=int(call['caller'],16)&0x3fffff
                    if image[pc]!=0x20 or int.from_bytes(image[pc+1:pc+3],'little')!=int(call['callee'],16)&65535:
                        raise ValueError('Main call preimage differs')
                iterations.append(dict(start=rows[i],fade=fade,calls=calls,
                    start_offset=rows[i]['frame']-enable,fade_offset=fade['frame']-enable,
                    master_clocks=fade['clock']-rows[i]['clock']))
            audio=[];producers=[]
            for i,r in enumerate(rows):
                if not enable<=r['frame']<enable+10:continue
                if r['pc']==0xc00000+labels['audio_publish_bridge']:
                    end=return_index(rows,i,0x6b)
                    audio.append(dict(entry=r,after=rows[end],**audio_sections(rows,i,end,labels)))
                elif r['pc']==0xc00000+labels['native_prepare']:
                    end=return_index(rows,i,0x60)
                    producers.append(dict(entry=r,after=rows[end],phases=prepare_phases(rows,i,end,labels),
                        hidden_rows=sum(x['pc']==0xc00000+labels['prepare_hidden_direct_row'] for x in rows[i:end])))
            if not audio or not producers:raise ValueError('Missing native audio/producer coverage')
        paths.append(trace)
        systems[name]=dict(enable_frame=enable,rom_sha256=receipt['rom_sha256'],iterations=iterations,
            audio=audio,producers=producers,timeline=[dict(offset=i,frame=r['frame'],
                fade_flags=bytes.fromhex(r['game_ram_hex'])[0x3e],fade_level=bytes.fromhex(r['game_ram_hex'])[0x692],
                fade_tick=bytes.fromhex(r['game_ram_hex'])[0x693],nmi_tick=bytes.fromhex(r['game_ram_hex'])[0x10b],
                transition=r.get('native',{}).get('transition_state')) for i,r in enumerate(timeline[index:index+16])])
    paths.extend((Path('.deps/snes9x/cpuexec.cpp'),Path('.deps/fceumm-raster/src/x6502.c')))
    report=dict(sources={str(p):sha(p) for p in paths},systems=systems,observer_neutral=True,
        scope='First four complete mall main-to-fade iterations. Full-capture neutrality for each observer. '
              'Audio waits partitioned inside sender inside bridge; do not add nested costs. Wait routine '
              'elapsed time includes checks/returns, not exclusively stalled CPU. Different builds have '
              'different encounters/timing; this is not a controlled attribution of all differences to SPC. '
              'NES cycles and SNES clocks are different units; NES reported line240 is not a precise beam. '
              'No game modification, deployment, gate waiver, or acoustic claim.')
    out.mkdir(parents=True,exist_ok=False);(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    table=[];summary={}
    for name,s in systems.items():
        offsets=[(r['points'][0]['offset'],r['points'][6]['offset']) if name=='NES' else
            (r['start_offset'],r['fade_offset']) for r in s['iterations']]
        summary[name]=dict(offsets=offsets)
        for i,(a,b) in enumerate(offsets):table.append(f'<tr><td>{name}</td><td>{i+1}</td><td>{a}</td><td>{b}</td></tr>')
        if name!='NES':
            packets=[a for a in s['audio'] if a['packet']]
            summary[name]['audio']={k:[min(a[k] for a in packets),max(a[k] for a in packets)] for k in
                ('bridge_clocks','sender_clocks','wait_clocks','bridge_outside_sender')}
            summary[name]['ready_wait']=[min(a['waits'][0]['clocks'] for a in packets),max(a['waits'][0]['clocks'] for a in packets)]
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Mall fade scheduling</title>'
        '<style>body{font:17px sans-serif;background:#101821;color:#eee;margin:30px}td,th{padding:8px;border:1px solid #567}a{color:#8df}</style>'
        '<h1>Mall fade scheduling and sound-wait costs</h1><p>'+html.escape(report['scope'])+'</p>'
        '<table><tr><th>Build</th><th>Iteration</th><th>Main offset</th><th>Fade service offset</th></tr>'+''.join(table)+
        '</table><pre>'+html.escape(json.dumps(summary,indent=2))+'</pre><p><a href="report.json">Exact calls, audio waits, row phases and source hashes</a></p>')
    print(json.dumps(summary))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True)
    audit(**vars(p.parse_args()))
