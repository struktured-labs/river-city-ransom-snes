"""Bind the first room-2 sprite-list call's elapsed cost to neutral execution."""
import argparse
from collections import Counter
import csv
import json
from pathlib import Path

try:
    from .benchmark_report import verify_capture, sha
    from .audit_room_entry import entries
    from .audit_park_instructions import parse, section
except ImportError:
    from benchmark_report import verify_capture, sha
    from audit_room_entry import entries
    from audit_park_instructions import parse, section


def interrupt_accounting(selected,nmi_events):
    """Subtract only completely observed ordinary NMIs with matched stacks."""
    interrupts=[];ranges=[]
    for j,r in enumerate(selected):
        if r['clock'] not in nmi_events:continue
        if r['pc']!=nmi_events[r['clock']]:raise ValueError('NMI stage/instruction mismatch')
        returns=[k for k in range(j+1,len(selected)-1)
            if selected[k]['opcode']==0x40 and selected[k]['s']==r['s']]
        if not returns:raise ValueError('No matching ordinary RTI inside call')
        k=returns[0];after=selected[k+1]
        if after['s']!=0x100|((r['s']+3)&255):raise ValueError('RTI did not restore emulation stack')
        if any(x['clock'] in nmi_events for x in selected[j+1:k+1]):raise ValueError('Nested NMI needs a different accounting model')
        ranges.append((r['clock'],after['clock']))
        interrupts.append(dict(first_frame=r['frame'],last_frame=after['frame'],
            clocks=after['clock']-r['clock'],entry_stack=r['s'],restored_stack=after['s']))
    costs=Counter()
    for a,b in zip(selected,selected[1:]):
        if any(start<=a['clock']<end for start,end in ranges):continue
        pc=a['pc'];key=f'runtime:{pc&65535:04x}' if pc>>16!=0xc0 and 0x2000<=pc&65535<0x3000 else f'{pc:06x}'
        costs[key]+=b['clock']-a['clock']
    elapsed=selected[-1]['clock']-selected[0]['clock'];nmi=sum(i['clocks'] for i in interrupts)
    if sum(costs.values())+nmi!=elapsed:raise ValueError('Interrupt accounting does not partition call')
    return dict(ordinary_nmi_spans=interrupts,ordinary_nmi_clocks=nmi,outside_ordinary_nmi_clocks=elapsed-nmi,
        outside_nmi_instruction_elapsed=[dict(pc=pc,clocks=clocks) for pc,clocks in costs.most_common(30)])


def main_call_sections(rows,first,fade,nmi_events):
    start=next(i for i,r in enumerate(rows) if r['pc']==0xc7f293 and r['frame']>=first)
    stack=rows[start]['s'];calls=[]
    for i in range(start,len(rows)-1):
        r=rows[i]
        if r['clock']>=fade['clock']:break
        if r['opcode']!=0x20 or r['s']!=stack or not 0xf293<=r['pc']&65535<=0xf2b4:continue
        if not 0xc1<=r['pc']>>16<=0xc8:raise ValueError('Main call outside replicated game banks')
        end=next((v for v in rows[i+1:] if v['pc']&65535==(r['pc']+3)&65535 and v['s']==stack
            and 0xc1<=v['pc']>>16<=0xc8),None)
        if end is None:raise ValueError('Truncated main-loop call')
        cost,selected=section(rows,r['clock'],end['clock'])
        cost.update(interrupt_accounting(selected,nmi_events))
        calls.append(dict(caller=f'{r["pc"]:06x}',callee=f'{rows[i+1]["pc"]:06x}',return_pc=f'{end["pc"]:06x}',
            first_frame=r['frame'],last_frame=end['frame'],cost=cost))
    if [int(c['caller'],16)&65535 for c in calls]!=list(range(0xf293,0xf2b5,3)):
        raise ValueError('First main-loop call sequence differs')
    return calls


def palette_copy_sections(rows, first):
    """Exact original 32-byte E477 palette-copy loops, not arbitrary windows."""
    copies=[]
    for i,start in enumerate(rows):
        if (start['frame']<first or start['pc']!=0xc7e477 or start['x']!=0):
            continue
        end=next((j for j in range(i+1,len(rows)) if rows[j]['pc']==0xc7e482
                  and rows[j]['s']==start['s']),None)
        if end is None:raise ValueError('Truncated palette-copy loop')
        selected=rows[i:end+1]
        loads=[r for r in selected if r['pc']==0xc7e477 and r['s']==start['s']]
        if ([r['x'] for r in loads]!=list(range(32)) or
            any(r['opcode']!=0xbd for r in loads) or rows[end]['x']!=32):
            raise ValueError('Original palette-copy sequence differs')
        cost,_=section(rows,start['clock'],rows[end]['clock'])
        copies.append(dict(start=start,end=rows[end],cost=cost))
    if not copies:raise ValueError('Missing complete palette-copy loops')
    return copies


def audit(capture,control,trace,spans,out):
    receipt,frames=verify_capture(capture)
    baseline,_=verify_capture(control)
    for key in ('rom_sha256','scenario_sha256','timeline_sha256','audio_sha256','frames'):
        if receipt[key]!=baseline[key]:raise ValueError('Timing observer changed execution: '+key)
    if not receipt['capture_complete'] or receipt['system']!='snes' or any(r['fault'] for r in frames):
        raise ValueError('Incomplete or faulty game capture')
    binding=receipt['instruction_trace']
    if binding['sha256']!=sha(trace):raise ValueError('Unbound instruction trace')
    if receipt.get('span_trace',{}).get('sha256')!=sha(spans):raise ValueError('Unbound stage trace')
    rows=parse(csv.reader(trace.open()),binding['first'],binding['last'])
    events=list(csv.reader(spans.open()))
    if any(len(r)!=16 for r in events):raise ValueError('Wrong stage trace schema')
    nmi_events={int(r[4]):int(r[5],16) for r in events if int(r[0])==0}
    if not nmi_events or len(set(nmi_events.values()))!=1:raise ValueError('Missing or ambiguous NMI entry')
    enable=frames[entries(frames)[2]]['frame']
    if binding['first']>enable:raise ValueError('Trace misses start of room entry')
    calls=[]
    for i,row in enumerate(rows):
        if row['pc']!=0xc7f293 or row['frame']<enable:continue
        if row['opcode']!=0x20 or rows[i+1]['pc']!=0xc7efd4:
            raise ValueError('Original F293 sprite-list call changed')
        returns=[r for r in rows[i+1:] if r['pc']==0xc7f296 and r['s']==row['s']]
        if not returns:raise ValueError('Truncated sprite-list call')
        end=returns[0]
        cost,selected=section(rows,row['clock'],end['clock'])
        cost.update(interrupt_accounting(selected,nmi_events))
        # Retain nested draw calls separately; inclusive timing can include NMI.
        draws=[]
        for j,r in enumerate(selected[:-1]):
            if r['pc']&65535!=0xf04b or r['opcode']!=0x20:continue
            matches=[x for x in selected[j+1:] if x['pc']&65535==0xf04e and x['s']==r['s']]
            if not matches:raise ValueError('Unmatched nested ED0E call')
            draws.append(dict(first_frame=r['frame'],last_frame=matches[0]['frame'],
                clocks=matches[0]['clock']-r['clock']))
        calls.append(dict(first_frame=row['frame'],last_frame=end['frame'],cost=cost,draw_calls=draws))
    if len(calls)<2:raise ValueError('Need first sprite-list call and a subsequent call')
    fade=[r for r in rows if r['pc']==0xc7e343 and r['frame']>=enable]
    if not fade:raise ValueError('Missing first original fade service')
    telemetry=[]
    for r in frames[entries(frames)[2]:entries(frames)[2]+16]:
        raw=bytes.fromhex(r['game_ram_hex'])
        telemetry.append(dict(frame=r['frame'],transition=r['native']['transition_state'],
            main_nmi_ticks=raw[0x10b],fade_flags_003e=raw[0x3e],fade_level_0692=raw[0x692],fade_tick_0693=raw[0x693]))
    report=dict(observer_equivalent=True,room2_enable_frame=enable,first_fade_instruction=fade[0],
        sprite_list_calls=calls,first_main_iteration_calls=main_call_sections(rows,enable,fade[0],nmi_events),telemetry=telemetry,
        palette_copy_calls=palette_copy_sections(rows,enable),
        sources=dict(capture_sha256=sha(capture/'capture.json'),control_sha256=sha(control/'capture.json'),
            trace_sha256=sha(trace),spans_sha256=sha(spans),rom_sha256=receipt['rom_sha256'],audit_sha256=sha(Path(__file__))),
        scope='Original main-loop F293 through F2B4 calls, repeated sprite-list calls and nested F04B -> ED0E -> F04E calls, '
              'matched by return PC and stack. Inclusive clocks contain interrupts and DMA; not exclusive actor CPU cost. '
              'NMI subtraction uses bound entry events and matching RTI stack restoration; residual clocks may still include DMA/events. '
              'Full timeline and PCM match the normal core. Fade service is observed, not moved or accelerated.')
    out.mkdir(parents=True,exist_ok=False)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(observer_equivalent=True,calls=[dict(first=c['first_frame'],last=c['last_frame'],
        clocks=c['cost']['master_clocks'],draws=c['draw_calls']) for c in calls]),indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('capture','control','trace','spans','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();audit(a.capture,a.control,a.trace,a.spans,a.out)
