"""Original NES and port main/fade service order after state-selected alley entry."""
import argparse
import csv
import html
import json
from pathlib import Path

from tools.audit_park_instructions import parse
from tools.audit_room_entry import entries
from tools.audit_room_load_profile import main_call_sections
from tools.benchmark_report import sha,verify_capture
from tools.nes_event_trace import validate

POINTS={str(i):f'{pc:04x}' for i,pc in enumerate((0xf293,0xf296,0xf299,0xf29c,0xf2a5,0xf2a8,0xe343,0xf2da))}


def nes_iterations(events,enable,count=3):
    starts=[i for i,r in enumerate(events) if r[3]=='0' and int(r[0])>=enable]
    if len(starts)<count:raise ValueError('Missing requested NES iterations')
    result=[]
    for start in starts[:count]:
        selected=events[start:start+8]
        if [int(r[3]) for r in selected]!=list(range(8)):
            raise ValueError('Missing, repeated or reordered NES call boundary')
        stack=int(selected[0][12])
        if any(int(r[12])!=((stack-2)&255 if i==6 else stack) for i,r in enumerate(selected)):
            raise ValueError('NES call boundary stack differs')
        points=[dict(frame=int(r[0]),offset=int(r[0])-enable,reported_line=int(r[1]),
            cpu_cycles=int(r[2]),pc=r[4],stack=int(r[12])) for r in selected]
        result.append(dict(points=points,main_to_fade_cpu_cycles=points[6]['cpu_cycles']-points[0]['cpu_cycles']))
    return result


def neutral(capture,normal):
    a,rows=verify_capture(capture);b,control=verify_capture(normal)
    if rows!=control or not a['capture_complete'] or any(a[k]!=b[k] for k in
            ('rom_sha256','audio_sha256','scenario_sha256','frames')):
        raise ValueError('Observer changed complete timeline or PCM')
    if any(r['fault'] or r['input_requested']!=r['input_delivered'] for r in rows):
        raise ValueError('Faulty route or input mismatch')
    return a,rows


def audit(out):
    sources={str(Path(__file__)):sha(Path(__file__))}
    paths=[Path('tools/audit_room_entry.py'),Path('tools/audit_room_load_profile.py'),
           Path('tools/audit_park_instructions.py'),Path('tools/nes_event_trace.py'),
           Path('tools/benchmark_report.py'),Path('tools/fceumm_queue_trace.inc'),Path('tools/snes9x_instruction_trace.inc')]
    systems={}
    for label,capture,normal,candidate in (
        ('NES','alley-nes-events-1402','park-single-nes-331',None),
        ('Current16','alley-entry-instructions-1374','postpublish-normal-1322','postpublish-keyon-1321'),
        ('Compact12','hidden-index12-instructions-1403','hidden-index12-normal-1392','hidden-index12-1391')):
        root=Path('build')/capture;base=Path('build')/normal
        receipt,timeline=neutral(root,base);index=entries(timeline)[1];enable=timeline[index]['frame']
        rom=Path('roms/river-city-ransom-us.nes') if candidate is None else Path('build')/candidate/'native-cpu.sfc'
        if sha(rom)!=receipt['rom_sha256']:raise ValueError('Different profiled cartridge')
        paths.extend([root/'capture.json',base/'capture.json',rom])
        if candidate is None:
            binding=receipt['nes_event_trace'];trace=Path(binding['path'])
            if binding['points']!=POINTS or sha(trace)!=binding['sha256']:
                raise ValueError('Wrong NES event sites or changed trace')
            with trace.open() as f:events=list(csv.reader(f))
            validate(events,binding['first'],binding['last'],receipt['frames'],POINTS)
            iterations=nes_iterations(events,enable)
        else:
            binding=receipt['instruction_trace'];trace=Path(binding['path'])
            if sha(trace)!=binding['sha256']:raise ValueError('Changed instruction trace')
            with trace.open() as f:rows=parse(csv.reader(f),binding['first'],binding['last'])
            label_path=rom.parent/'native_boot.lbl';paths.append(label_path)
            labels={r.split()[2].lstrip('.'):int(r.split()[1],16) for r in label_path.read_text().splitlines()}
            nmi=labels['nmi'];nmis={r['clock']:r['pc'] for r in rows if r['pc'] in (nmi,0xc00000+nmi)}
            starts=[i for i,r in enumerate(rows) if r['pc']==0xc7f293 and r['frame']>=enable]
            if len(starts)<3:raise ValueError('Missing three SNES iterations')
            image=rom.read_bytes();iterations=[]
            for i in starts[:3]:
                fade=next(r for r in rows[i:] if r['pc']==0xc7e343 and r['s']==rows[i]['s']-2)
                calls=main_call_sections(rows[i:],rows[i]['frame'],fade,nmis)
                for call in calls:
                    pc=int(call['caller'],16)&0x3fffff
                    if image[pc]!=0x20 or int.from_bytes(image[pc+1:pc+3],'little')!=int(call['callee'],16)&65535:
                        raise ValueError('Unexpected original call in cartridge')
                iterations.append(dict(start=rows[i],fade=fade,calls=calls,
                    start_offset=rows[i]['frame']-enable,fade_offset=fade['frame']-enable,
                    main_to_fade_master_clocks=fade['clock']-rows[i]['clock']))
        paths.append(trace)
        systems[label]=dict(enable_frame=enable,rom_sha256=receipt['rom_sha256'],iterations=iterations,
            timeline=[dict(offset=i,frame=r['frame'],fade_flags=bytes.fromhex(r['game_ram_hex'])[0x3e],
                fade_level=bytes.fromhex(r['game_ram_hex'])[0x692],fade_tick=bytes.fromhex(r['game_ram_hex'])[0x693],
                nmi_tick=bytes.fromhex(r['game_ram_hex'])[0x10b],transition=r.get('native',{}).get('transition_state'))
                for i,r in enumerate(timeline[index:index+16])])
    sources.update({str(p):sha(p) for p in paths})
    result=dict(observer_neutral=True,systems=systems,sources=sources,release_ready=False,
        scope='First three main iterations after state-selected alley rendering enable. NES exact-PC events; '
              'SNES complete instruction trace and matched ordinary-NMI subtraction. Every observer is neutral '
              'to its full original baseline timeline and PCM. NES cycles and SNES master clocks are different '
              'units, and encounters are not proven equal work. FCEU reported line240 persists during VBlank; '
              'it is not a precise physical start scanline. Fade service is not necessarily palette generation.')
    out.mkdir(parents=True,exist_ok=False);(out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    table=[]
    for label,system in systems.items():
        for i,r in enumerate(system['iterations']):
            start,fade=(r['points'][0]['offset'],r['points'][6]['offset']) if label=='NES' else (r['start_offset'],r['fade_offset'])
            table.append(f'<tr><td>{label}</td><td>{i+1}</td><td>+{start}</td><td>+{fade}</td></tr>')
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Alley fade service schedule</title>'
        '<style>body{font:17px system-ui;background:#101821;color:#eef;margin:32px}td,th{padding:9px;border:1px solid #567}a{color:#9df}</style>'
        '<h1>Alley fade service schedule</h1><p>'+html.escape(result['scope'])+'</p>'
        '<table><tr><th>Build</th><th>Iteration</th><th>Main start offset</th><th>Fade call offset</th></tr>'+
        ''.join(table)+'</table><p>Compact12 initializes the fade on the NES frame (+3), but its next service '
        'is +5 versus NES +4. The generation and visibility differences remain failures. No ROM change or Rival restart.</p>'
        '<p><a href="report.json">All calls, timeline values, NMI costs and source hashes</a></p>')
    print(json.dumps({k:[(r['points'][0]['offset'],r['points'][6]['offset']) if k=='NES' else
          (r['start_offset'],r['fade_offset']) for r in v['iterations']] for k,v in systems.items()}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True)
    audit(**vars(p.parse_args()))
