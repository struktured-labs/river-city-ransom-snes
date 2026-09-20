"""Measure pre-camera main calls, separating observed hardware-NMI spans."""
import argparse
from collections import defaultdict
import csv
import json
from pathlib import Path

from tools.audit_park_instructions import parse
from tools.audit_room_load_profile import interrupt_accounting
from tools.benchmark_report import sha,verify_capture

CALLERS={0xf282:'controls',0xf28b:'C125',0xf293:'sprite construction',
         0xf296:'DFE2',0xf299:'actor update',0xf29c:'E095',0xf29f:'FAE9'}


def measure(rows,nmis):
    calls=[];censored=[]
    for i,start in enumerate(rows):
        pc=start['pc']&65535
        if not 0xc1<=start['pc']>>16<=0xc8 or pc not in CALLERS:continue
        if start['opcode']!=0x20:raise ValueError('Main call opcode changed')
        end=next((j for j in range(i+1,len(rows)) if rows[j]['pc']&65535==pc+3
            and rows[j]['s']==start['s'] and 0xc1<=rows[j]['pc']>>16<=0xc8),None)
        if end is None:
            censored.append(dict(caller=pc,start=start,kind='trailing incomplete call'))
            continue
        chosen=rows[i:end+1];cost=interrupt_accounting(chosen,nmis)
        calls.append(dict(caller=pc,name=CALLERS[pc],start=start,end=rows[end],
            elapsed_clocks=rows[end]['clock']-start['clock'],**cost))
    if not calls:raise ValueError('No complete main calls')
    by=defaultdict(list)
    for call in calls:by[call['caller']].append(call)
    summary={f'{pc:04x}':dict(name=CALLERS[pc],count=len(values),**{
        'mean_'+key:sum(v[key] for v in values)/len(values) for key in
        ('elapsed_clocks','ordinary_nmi_clocks','outside_ordinary_nmi_clocks')}) for pc,values in by.items()}
    return dict(calls=calls,censored=censored,summary=summary)


def audit(capture,normal,candidate,out):
    receipt,rows=verify_capture(capture);control,baseline=verify_capture(normal)
    if rows!=baseline or not receipt['capture_complete'] or any(receipt[k]!=control[k]
            for k in ('rom_sha256','scenario_sha256','audio_sha256','frames')):
        raise ValueError('Observer changed complete execution')
    rom=candidate/'native-cpu.sfc'
    if sha(rom)!=receipt['rom_sha256']:raise ValueError('Wrong cartridge')
    binding=receipt['instruction_trace'];trace=Path(binding['path'])
    span_binding=receipt['span_trace'];spans=Path(span_binding['path'])
    if sha(trace)!=binding['sha256'] or sha(spans)!=span_binding['sha256']:raise ValueError('Changed bound trace')
    with trace.open() as stream:instructions=parse(csv.reader(stream),binding['first'],binding['last'])
    with spans.open() as stream:events=list(csv.reader(stream))
    if any(len(r)!=16 for r in events):raise ValueError('Wrong span schema')
    nmis={int(r[4]):int(r[5],16) for r in events if int(r[0])==0}
    labels={r.split()[2].lstrip('.'):int(r.split()[1],16)
        for r in (candidate/'native_boot.lbl').read_text().splitlines()}
    if not nmis or set(nmis.values())!={labels['nmi']}:raise ValueError('Missing/wrong hardware NMI entry')
    report=measure(instructions,nmis)
    if {c['caller'] for c in report['calls']}!=set(CALLERS):raise ValueError('Incomplete caller coverage')
    paths=[Path(__file__),Path('tools/audit_park_instructions.py'),Path('tools/audit_room_load_profile.py'),
        Path('tools/benchmark_report.py'),capture/'capture.json',normal/'capture.json',rom,
        candidate/'native_boot.lbl',trace,spans]
    report.update(passed=True,observer_neutral=True,release_ready=False,sources={str(p):sha(p) for p in paths},
        scope='All complete observed original pre-camera JSR calls, return PC and emulation stack matched. '
        'Hardware NMI entries through stack-matched RTI subtracted; entry-edge clocks and DMA/events can remain outside. '
        'Camera hook excluded because it may execute retained original-NMI work. Censored trailing calls retained. '
        'Different encounters prohibit interpreting between-build actor means as equal-work speed ratios.')
    out.mkdir(parents=True,exist_ok=False);(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report['summary'],indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('capture','normal','candidate','out'):p.add_argument('--'+name,type=Path,required=True)
    audit(**vars(p.parse_args()))
