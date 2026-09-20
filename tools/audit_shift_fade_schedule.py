"""Explain both early and late fades using unchanged exact-PC timing observers."""
import argparse
import csv
import html
import json
from pathlib import Path

from tools.audit_alley_fade_schedule import neutral
from tools.audit_alley_entry_work import return_index, prepare_phases
from tools.audit_park_instructions import parse
from tools.audit_room_entry import entries
from tools.audit_room_load_profile import main_call_sections
from tools.benchmark_report import sha


def marks(rows, enable, entry):
    names={entry:'reset',0xf293:'first-call',0xe343:'fade',0xf2c9:'wait',0xf2da:'finish'}
    result=[]
    for row in rows:
        pc=row['pc'];name=names.get(pc&65535)
        if not name or not 0xc1<=pc>>16<=0xc8 or not enable<=row['frame']<enable+8:
            continue
        if name=='wait' and result and result[-1]['name']=='wait':continue
        result.append(dict(name=name,offset=row['frame']-enable,**row))
    if not all(any(r['name']==n for r in result) for n in names.values()):
        raise ValueError('Missing main/fade/wait/finish boundary')
    return result


def audit(out):
    specs=(('parent-alley','dispatch-alley-instructions-1959','receiver-dispatch-normal-1918','receiver-dispatch-1916',1),
        ('shift-alley','shift-alley-instructions-1960','signed-shift-route-1949','signed-shift-trial-1947',1),
        ('parent-mall','receiver-dispatch-trial-instructions-1924','receiver-dispatch-normal-1918','receiver-dispatch-1916',2),
        ('shift-mall','shift-mall-instructions-1961','signed-shift-route-1949','signed-shift-trial-1947',2))
    paths=[Path(__file__),*[Path('tools')/n for n in ('audit_alley_fade_schedule.py',
        'audit_alley_entry_work.py','audit_park_instructions.py','audit_room_entry.py',
        'audit_room_load_profile.py','benchmark_report.py','snes9x_instruction_trace.inc')],
        Path('.deps/snes9x/cpuexec.cpp')]
    runs={};cards=[]
    for name,cap,base,rom,room in specs:
        cap,base,rom=(Path('build')/x for x in (cap,base,rom))
        receipt,timeline=neutral(cap,base);binding=receipt['instruction_trace']
        trace=Path(binding['path']);image=(rom/'native-cpu.sfc').read_bytes()
        if sha(trace)!=binding['sha256'] or sha(rom/'native-cpu.sfc')!=receipt['rom_sha256']:
            raise ValueError('Changed profiled cartridge or instructions')
        with trace.open() as f:rows=parse(csv.reader(f),binding['first'],binding['last'])
        enable=timeline[entries(timeline)[room]]['frame']
        symbols={s.split()[2].lstrip('.'):int(s.split()[1],16) for s in (rom/'native_boot.lbl').read_text().splitlines()}
        runtime={s.split()[2].lstrip('.'):int(s.split()[1],16) for s in (rom/'native_runtime.lbl').read_text().splitlines()}
        nmi=symbols['nmi'];nmis={r['clock']:r['pc'] for r in rows if r['pc'] in (nmi,0xc00000+nmi)}
        starts=[i for i,r in enumerate(rows) if r['pc']==0xc7f293 and r['frame']>=enable]
        if len(starts)<3:raise ValueError('Missing first three complete main iterations')
        iterations=[]
        for i in starts[:3]:
            start=rows[i]
            fade=next(r for r in rows[i:] if r['pc']==0xc7e343 and r['s']==start['s']-2)
            calls=main_call_sections(rows[i:],start['frame'],fade,nmis)
            for c in calls:
                at=int(c['caller'],16)&0x3fffff
                if image[at]!=0x20 or int.from_bytes(image[at+1:at+3],'little')!=int(c['callee'],16)&65535:
                    raise ValueError('Changed original call site')
            iterations.append(dict(start=start,fade=fade,calls=calls,
                start_offset=start['frame']-enable,fade_offset=fade['frame']-enable,
                elapsed_master_clocks=fade['clock']-start['clock']))
        producers=[]
        for i,r in enumerate(rows):
            if r['pc']!=0xc00000+symbols['native_prepare'] or not enable<=r['frame']<enable+6:continue
            end=return_index(rows,i,0x60)
            producers.append(dict(entry=r,after=rows[end],offset=r['frame']-enable,
                phases=prepare_phases(rows,i,end,symbols)))
        events=marks(rows,enable,runtime['gameplay_iteration_start'])
        runs[name]=dict(enable=enable,iterations=iterations,producers=producers,marks=events,
            rom_sha256=receipt['rom_sha256'],observer_neutral=True)
        paths.extend((cap/'capture.json',base/'capture.json',rom/'native-cpu.sfc',
                      rom/'native_boot.lbl',rom/'native_runtime.lbl',trace))
        cards.append(f'<h2>{name}</h2><table><tr><th>Event</th><th>Frame offset</th><th>Scanline</th><th>Cycle</th></tr>')
        cards.extend(f'<tr><td>{e["name"]}</td><td>{e["offset"]}</td><td>{e["line"]}</td><td>{e["cycle"]}</td></tr>' for e in events)
        cards.append('</table>')
    report=dict(runs=runs,sources={str(p):sha(p) for p in paths},release_ready=False,deployed=False,
        scope='Three main-to-fade calls per room/build, matched stack and exact call preimages. '
              'Each complete observed route equals its own normal timeline and PCM. '
              'NES-equivalent actor work is not established; do not attribute encounter changes '
              'to graphics scheduling or change fade counters to force a match. NMI subtraction '
              'is diagnostic; no time is deducted from whole-load acceptance.')
    out.mkdir(parents=True,exist_ok=False)
    page='''<!doctype html><meta charset="utf-8"><title>Early and late fade timing</title>
<style>body{background:#101821;color:#eef;font:17px system-ui;max-width:1100px;margin:30px auto}
td,th{padding:8px;border:1px solid #567}a{color:#8df}</style>
<h1>Two different post-load timing paths</h1>
<p>Alley: parent finishes and resets on enable+3, scanline239. Shift trial reaches
the fade a little later, crosses an interrupt, and finishes/resets on enable+4.
Its third main iteration starts on +6 rather than +5.</p>
<p>Mall: the trial actor call has 50,136 elapsed clocks outside ordinary NMIs,
versus parent158,072. These are different encounters/workloads, not proof that
the arithmetic change alone saved that much CPU time. The early fade and failed
fixed-offset comparison remain failures; no gate is waived.</p>'''
    page+='<p>'+html.escape(report['scope'])+'</p>'+''.join(cards)
    page+='<p><a href="report.json">Full instructions, nested call costs, and producer phases</a> · <a href="../signed-shift-entry-1953/">Retained NES comparison failures</a></p>'
    (out/'index.html').write_text(page)
    report['artifacts']={'index.html':sha(out/'index.html')}
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(out=str(out),runs=len(runs),observer_neutral=True)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True)
    audit(**vars(p.parse_args()))
