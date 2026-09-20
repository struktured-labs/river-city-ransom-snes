"""Account for complete game iterations, not just delivered native interrupts."""
import argparse
from collections import Counter
import csv
import json
from pathlib import Path

from tools.benchmark_report import sha, verify_capture


def pair(records, points, first, last):
    active=None; completed=[]; censored=[]; previous=-1
    for raw in records:
        if len(raw)!=16:raise ValueError('Need exact-clock sixteen-column observations')
        values=[int(v,16 if i==5 else 10) for i,v in enumerate(raw)]
        event,frame,line,cycle,clock,pc,nmi,task,transition,guard,room,pause,*_=values
        if (event not in points or pc>>16 not in range(0xc1,0xc9) or
            pc&65535!=points[event] or not first<=frame<=last or
            not 0<=line<262 or clock<=previous):
            raise ValueError('Invalid PC, frame, beam or event ordering')
        previous=clock
        record=dict(frame=frame,line=line,cycle=cycle,clock=clock,nmi=nmi,
                    task=task,transition=transition,guard=guard,room=room,pause=pause)
        if event==0:
            if active is not None:raise ValueError('Iteration restarted before completion')
            active=dict(start=record,input=None)
        elif event==1:
            if active is None or active['input'] is not None:
                raise ValueError('Input entry without a unique iteration start')
            active['input']=record
        elif active is None:
            censored.append(dict(kind='leading completion',event=record))
        else:
            if active['input'] is None:raise ValueError('Iteration omitted input sampling')
            completed.append(dict(**active,finish=record,
                nmi_advances=(record['nmi']-active['start']['nmi'])&65535,
                elapsed_clocks=clock-active['start']['clock']))
            active=None
    if active is not None:censored.append(dict(kind='trailing iteration',event=active))
    if not completed:raise ValueError('No complete iterations')
    return completed,censored


def eligible(rows):
    for row in rows:
        ram=bytes.fromhex(row['game_ram_hex'])
        if (ram[0x42]!=3 or ram[0x100]!=0xc0 or ram[0x107]&128 or
            ram[0x3f]&32 or ram[0x3e]&130 or ram[0x692]!=4 or
            row['native']['transition_state']):return False
    return bool(rows)


def audit(capture,normal,candidate,out):
    receipt,rows=verify_capture(capture);control,baseline=verify_capture(normal)
    if not receipt['capture_complete'] or rows!=baseline or any(receipt[k]!=control[k] for k in
        ('rom_sha256','scenario_sha256','audio_sha256','frames')):
        raise ValueError('Incomplete/non-neutral loop observer')
    rom=candidate/'native-cpu.sfc';labels=candidate/'native_runtime.lbl'
    if sha(rom)!=receipt['rom_sha256']:raise ValueError('Wrong cartridge')
    symbols={s.split()[2].lstrip('.'):int(s.split()[1],16) for s in labels.read_text().splitlines()}
    points={0:symbols['gameplay_iteration_start'],1:0xf282,2:0xf2da}
    image=rom.read_bytes()
    for pc,data in ((0xf282,bytes.fromhex('2031f7')),(0xf2da,bytes.fromhex('ee2b05'))):
        if image[0x10000+pc:0x10000+pc+3]!=data:raise ValueError('Main instruction differs')
    binding=receipt['span_trace'];trace=Path(binding['path'])
    if (sha(trace)!=binding['sha256'] or binding['points']!={str(k):f'{v:04x}' for k,v in points.items()}):
        raise ValueError('Wrong/unbound iteration observation points')
    with trace.open() as stream:
        loops,censored=pair(csv.reader(stream),points,binding['first'],binding['last'])
    selected=[];excluded=[]
    for loop in loops:
        (selected if eligible(rows[loop['start']['frame']-1:loop['finish']['frame']]) else excluded).append(loop)
    if not selected:raise ValueError('No fully observed stable park iterations')
    starts=[dict(before=a['start']['frame'],after=b['start']['frame'],
                 clocks=b['start']['clock']-a['start']['clock'])
            for a,b in zip(selected,selected[1:])
            if eligible(rows[a['start']['frame']-1:b['start']['frame']])]
    result=dict(release_ready=False,observer_neutral=True,iterations=selected,
        nmi_advances=dict(Counter(r['nmi_advances'] for r in selected)),
        over_two_ticks=[r for r in selected if r['nmi_advances']>2],
        start_intervals=starts,censored=censored,excluded=excluded,
        sources={str(p):sha(p) for p in (Path(__file__),Path('tools/benchmark_report.py'),
            capture/'capture.json',normal/'capture.json',trace,rom,labels)},
        scope='Complete main-entry/input-call/F2DA completion pairs; delivered NMI counts and clocks. '
              'All non-stable-park iterations retained separately. Not matched-combat or NES input latency.')
    out.mkdir(parents=True,exist_ok=False)
    (out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(stable_iterations=len(selected),nmi_advances=result['nmi_advances'],
        over_two_ticks=len(result['over_two_ticks']),
        start_frame_spans=dict(Counter(x['after']-x['before'] for x in starts)))))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('capture','normal','candidate','out'):parser.add_argument('--'+name,required=True,type=Path)
    audit(**vars(parser.parse_args()))
