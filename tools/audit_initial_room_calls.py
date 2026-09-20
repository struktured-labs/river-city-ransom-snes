"""Measure the first gameplay iteration after a room's rendering-enable edge."""
import argparse
import csv
import json
from pathlib import Path

from tools.audit_room_load_profile import main_call_sections
from tools.audit_park_instructions import parse
from tools.audit_room_entry import entries
from tools.benchmark_report import verify_capture,sha


def audit(capture,normal,trace,spans,rom,room,out,iteration=0):
    receipt,frames=verify_capture(capture);control,_=verify_capture(normal)
    if (receipt['system']!='snes' or not receipt['capture_complete'] or any(r['fault'] for r in frames)
        or any(r['input_requested']!=r['input_delivered'] for r in frames)):
        raise ValueError('Need a complete fault-free input replay')
    for key in ('rom_sha256','scenario_sha256','timeline_sha256','audio_sha256','frames'):
        if receipt[key]!=control[key]:raise ValueError('Observer changed execution: '+key)
    if sha(rom)!=receipt['rom_sha256']:raise ValueError('Unbound ROM')
    binding=receipt['instruction_trace']
    if sha(trace)!=binding['sha256'] or sha(spans)!=receipt['span_trace']['sha256']:
        raise ValueError('Unbound instruction/stage trace')
    with trace.open() as f:rows=parse(csv.reader(f),binding['first'],binding['last'])
    with spans.open() as f:events=list(csv.reader(f))
    if any(len(r)!=16 for r in events):raise ValueError('Bad stage schema')
    nmis={int(r[4]):int(r[5],16) for r in events if r[0]=='0'}
    if not nmis or len(set(nmis.values()))!=1:raise ValueError('Missing unique NMI entry')
    enable=frames[entries(frames)[room]]['frame']
    if binding['first']>enable:raise ValueError('Missing initial room edge')
    starts=[i for i,r in enumerate(rows) if r['pc']==0xc7f293 and r['frame']>=enable]
    if not 0<=iteration<len(starts):raise ValueError('Requested iteration is outside the observed window')
    start=starts[iteration]
    fade=next(r for r in rows[start:] if r['pc']==0xc7e343 and r['s']==rows[start]['s']-2)
    calls=main_call_sections(rows[start:],rows[start]['frame'],fade,nmis)
    image=rom.read_bytes()
    for call in calls:
        pc=int(call['caller'],16)&0x3fffff
        if image[pc]!=0x20 or int.from_bytes(image[pc+1:pc+3],'little')!=(int(call['callee'],16)&65535):
            raise ValueError('Main call not backed by actual cartridge opcode')
    report=dict(room=room,enable_frame=enable,iteration=iteration,iteration_start=rows[start],
        first_fade_service=fade,first_main_calls=calls,
        observer_neutral=True,
        sources={str(p):sha(p) for p in (capture/'capture.json',normal/'capture.json',trace,spans,rom,
            Path(__file__),Path(__file__).with_name('audit_room_load_profile.py'))},
        scope='Actual F293..F2B4 calls in the selected zero-based iteration after rendering-enable, '
              'with matched call/return stacks and ordinary-NMI subtraction. A fade-service call is '
              'not necessarily a palette generation or first visible color. '
              'Residual clocks can include DMA/events, not exclusive CPU instruction cost. '
              'Entire primary timeline and PCM match normal replay.')
    out.mkdir(parents=True,exist_ok=False)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(room=room,enable_frame=enable,calls=[dict(callee=c['callee'],
        clocks=c['cost']['master_clocks'],nmi=c['cost']['ordinary_nmi_clocks'],
        residual=c['cost']['outside_ordinary_nmi_clocks']) for c in calls]),indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('capture','normal','trace','spans','rom','out'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--room',type=int,choices=(1,2,3),required=True)
    p.add_argument('--iteration',type=int,default=0)
    audit(**vars(p.parse_args()))
