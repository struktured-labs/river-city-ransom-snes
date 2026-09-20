"""Locate executed single-slot retained fallback in an authenticated stalled interval."""
import argparse
import csv
import json
from pathlib import Path

from tools.audit_main_display_latency import bound_report
from tools.audit_queued_read_poll import decode
from tools.benchmark_report import sha
from tools.build_retained_producer_guard import symbols


def audit(review,candidate,instructions,out):
    if out.exists():raise ValueError('Fresh output required')
    proof=bound_report(review/'report.json')
    trace=instructions.with_suffix('.csv');rom=candidate/'native-cpu.sfc'
    for p in (trace,rom,candidate/'native_boot.lbl'):
        if proof['sources'].get(str(p))!=sha(p):raise ValueError('Unbound input')
    boot=symbols(candidate/'native_boot.lbl');pc=boot['@deferred_fallback']
    wanted=bytes.fromhex('9ce01ceee41cd003eee51ceee61cd003eee71c68dc001c')
    if rom.read_bytes()[pc:pc+len(wanted)]!=wanted:
        raise ValueError('Fallback no longer clears one retained slot and directly dispatches one body')
    with trace.open() as stream:rows=[decode(r) for r in csv.reader(stream)]
    results=[]
    for interval in proof['remaining_intervals']:
        if not interval['every_frame_had_hardware_nmi']:
            raise ValueError('Different stall classification')
        chosen=[r for r in rows if interval['start']['clock']<=r['clock']<interval['next_start']['clock']]
        fallbacks=[r for r in chosen if r['pc']==pc]
        original=[r for r in chosen if 0xc1<=r['pc']>>16<=0xc8 and r['pc']&65535==0xff4f]
        hardware=[r for r in chosen if r['pc']==boot['nmi']]
        if len(fallbacks)!=1 or len(original)!=2 or len(hardware)!=3:
            raise ValueError('Different dispatch pattern')
        index=chosen.index(fallbacks[0])
        results.append(dict(start=interval['start'],next_start=interval['next_start'],
            fallback=fallbacks[0],hardware_entries=hardware,original_body_entries=original,
            branch_context=chosen[max(0,index-3):index+13]))
    paths=[Path(__file__),Path('tools/audit_queued_read_poll.py'),Path('snes/native_boot.asm'),
           review/'report.json',trace,rom,candidate/'native_boot.lbl']
    sources={**proof['sources'],**{str(p):sha(p) for p in paths}}
    report=dict(executed_single_slot_fallback=True,intervals=results,sources=sources,
        release_ready=False,scope=__doc__+' ROM bytes clear the old pending slot and directly '
        'dispatch one body. The source explicitly leaves the current event unscheduled. '
        'Three hardware entries but two body entries are observed here. This is a repair target, '
        'not proof that this is the only cause of slowdown or that merely adding a tick is safe.')
    out.mkdir(parents=True);(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(fallbacks=[r['fallback'] for r in results])))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for k in ('review','candidate','instructions','out'):parser.add_argument('--'+k,type=Path,required=True)
    audit(**vars(parser.parse_args()))
