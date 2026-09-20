"""Bound instruction timing for complete main-start to camera-store intervals."""
import argparse
import csv
import json
from pathlib import Path

from tools.audit_park_instructions import parse
from tools.benchmark_report import sha, verify_capture


def audit(capture, normal, candidate, out):
    receipt, rows=verify_capture(capture);control, baseline=verify_capture(normal)
    if rows!=baseline or not receipt['capture_complete'] or any(receipt[k]!=control[k]
            for k in ('rom_sha256','scenario_sha256','audio_sha256','frames')):
        raise ValueError('Instruction observer changed execution')
    rom=candidate/'native-cpu.sfc'
    if sha(rom)!=receipt['rom_sha256']:raise ValueError('Different cartridge')
    labels={s.split()[2].lstrip('.'):int(s.split()[1],16)
            for s in (candidate/'native_runtime.lbl').read_text().splitlines()}
    image=rom.read_bytes();entry=labels['gameplay_iteration_start'];commit=labels['camera_deferred_nmi_exit']+2
    if image[0x10000+commit:0x10000+commit+2]!=bytes.fromhex('85f6'):
        raise ValueError('Unknown camera-store instruction')
    binding=receipt['instruction_trace'];trace=Path(binding['path'])
    if sha(trace)!=binding['sha256']:raise ValueError('Changed instruction trace')
    with trace.open() as stream:instructions=parse(csv.reader(stream),binding['first'],binding['last'])
    active=None;intervals=[];censored=[]
    for r in instructions:
        if not 0xc1<=r['pc']>>16<=0xc8:continue
        pc=r['pc']&65535
        if pc==entry:
            if active is not None:raise ValueError('Unfinished main iteration before next start')
            active={k:r[k] for k in ('frame','line','cycle','clock')}
        elif pc==commit:
            event={k:r[k] for k in ('frame','line','cycle','clock')}
            if r['opcode']!=0x85:raise ValueError('Different executed store')
            event['camera_low']=r['a']&255
            if active is None:censored.append(dict(kind='leading camera',event=event))
            else:
                intervals.append(dict(start=active,commit=event,elapsed_clocks=r['clock']-active['clock']))
                active=None
    if active is not None:censored.append(dict(kind='trailing start',event=active))
    if not intervals:raise ValueError('No complete main intervals')
    report=dict(passed=True,observer_neutral=True,release_ready=False,intervals=intervals,censored=censored,
        main_start_lines=[min(r['start']['line'] for r in intervals),max(r['start']['line'] for r in intervals)],
        camera_store_lines=[min(r['commit']['line'] for r in intervals),max(r['commit']['line'] for r in intervals)],
        sources={str(p):sha(p) for p in (Path(__file__),Path('tools/audit_park_instructions.py'),
            Path('tools/benchmark_report.py'),capture/'capture.json',normal/'capture.json',trace,rom,
            candidate/'native_runtime.lbl')},
        scope='All complete main-start/camera-store pairs in the captured window; censored boundaries retained. Includes interrupts; different encounters prohibit an equal-work speed ratio.')
    out.mkdir(parents=True,exist_ok=False);(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('main_start_lines','camera_store_lines')}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('capture','normal','candidate','out'):p.add_argument('--'+name,required=True,type=Path)
    audit(**vars(p.parse_args()))
