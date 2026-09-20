"""Bind executed row-phase choices, main/camera timing and audio ACK observations."""
import argparse
from collections import Counter
import csv
import json
from pathlib import Path

from tools.audit_park_instructions import parse
from tools.analyze_spc_ack import analyze as analyze_ack
from tools.audit_park_execution import packet_gaps
from tools.benchmark_report import verify_capture,sha


def audit(capture,normal,candidate,full_spans,out):
    receipt,rows=verify_capture(capture);control,baseline=verify_capture(normal)
    full,full_rows=verify_capture(full_spans)
    for r,timeline in ((receipt,rows),(full,full_rows)):
        if not r['capture_complete'] or timeline!=baseline or any(r[k]!=control[k] for k in
                ('rom_sha256','scenario_sha256','audio_sha256','frames')):
            raise ValueError('Observer differs from complete normal execution')
    rom=candidate/'native-cpu.sfc'
    if sha(rom)!=receipt['rom_sha256']:raise ValueError('Wrong cartridge')
    labels={kind:{r.split()[2].lstrip('.'):int(r.split()[1],16)
        for r in (candidate/f'native_{kind}.lbl').read_text().splitlines()} for kind in ('boot','runtime')}
    binding=receipt['instruction_trace'];trace=Path(binding['path'])
    if sha(trace)!=binding['sha256']:raise ValueError('Unbound CPU trace')
    with trace.open() as stream:instructions=parse(csv.reader(stream),binding['first'],binding['last'])
    start=0xc00000+labels['boot']['visible_row_phase_budget']
    end=0xc00000+labels['boot']['prepare_fused_attribute_row']
    decisions=[];active=None;main=[];camera=[]
    image=rom.read_bytes()
    for i,r in enumerate(instructions):
        pc=r['pc']
        if pc==start:
            if active is not None:raise ValueError('Nested phase helper')
            active=dict(frame=r['frame'],line=r['line'],clock=r['clock'],tick=None)
        if start<=pc<end:
            if active is None:raise ValueError('Truncated phase helper entry')
            offset=pc&65535
            if image[offset]!=r['opcode']:raise ValueError('Wrong linked phase opcode')
            if image[offset:offset+3]==bytes.fromhex('ad0b01'):
                if i+1==len(instructions):raise ValueError('Missing tick read result')
                active['tick']=instructions[i+1]['a']&255
            if r['opcode']==0x60:
                budget=r['a']&255
                want=4 if active['tick']==1 else 0 if active['tick']==2 else 2
                if budget!=want:raise ValueError('Actual helper returned wrong tick budget')
                active.update(budget=budget,elapsed_clocks=r['clock']-active['clock'])
                decisions.append(active);active=None
        if pc>>16!=0xc0 and pc&65535==labels['runtime']['gameplay_iteration_start']:
            main.append({k:r[k] for k in ('frame','line','cycle','clock')})
        if pc>>16!=0xc0 and pc&65535==labels['runtime']['camera_deferred_nmi_exit']+2:
            if r['opcode']!=0x85:raise ValueError('Unexpected camera store')
            camera.append(dict(**{k:r[k] for k in ('frame','line','cycle','clock')},low_camera=r['a']&255))
    if active is not None or not decisions or not main or not camera:raise ValueError('Incomplete scheduling observations')
    ack_binding=full['spc_ack_trace'];ack=Path(ack_binding['path'])
    if sha(ack)!=ack_binding['sha256']:raise ValueError('Unbound ACK trace')
    with ack.open() as stream:audio=analyze_ack(csv.reader(stream),paired=True,
        engine_size=(candidate/'Memblers_2a03.bin').stat().st_size)
    gaps=packet_gaps(full_rows,audio)
    paths=[Path(__file__),Path('tools/audit_park_instructions.py'),Path('tools/analyze_spc_ack.py'),
        Path('tools/audit_park_execution.py'),Path('tools/benchmark_report.py'),trace,ack,rom,
        candidate/'native_boot.lbl',candidate/'native_runtime.lbl',candidate/'Memblers_2a03.bin',
        *[p/'capture.json' for p in (capture,normal,full_spans)]]
    report=dict(observer_neutral=True,release_ready=False,decisions=decisions,
        decision_histogram=dict(Counter(str(d['budget']) for d in decisions)),
        main_iteration_entries=main,camera_stores=camera,
        acknowledged_packets=audio['acknowledged_packets'],park_packet_gaps=gaps,
        stable_park_long_gaps=[g for g in gaps if g['stable_unpaused_park']],
        sources={str(p):sha(p) for p in paths},
        scope='Actual helper results and main/camera instruction beams in the bound CPU window; '
              'full-route audio ACKs. No equal-work combat, renderer release or acoustic certification.')
    out.mkdir(parents=True,exist_ok=False);(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(decisions=report['decision_histogram'],main_entries=len(main),
        packets=report['acknowledged_packets'],stable_park_long_gaps=len(report['stable_park_long_gaps']))))
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('capture','normal','candidate','full-spans','out'):p.add_argument('--'+name,type=Path,required=True)
    audit(**vars(p.parse_args()))
