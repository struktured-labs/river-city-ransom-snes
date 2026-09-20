"""Retain fresh-combat failure and authenticate full-route rendered pacing."""
import argparse
import csv
import json
from pathlib import Path

from tools import combat_campaign as combat
from tools.audit_busy_combat import measure
from tools.audit_display_cadence import observe
from tools.audit_main_display_latency import bound_report
from tools.audit_queued_read_poll import decode,interval_evidence
from tools.audit_uniform_holds import summarize
from tools.benchmark_report import sha,verify_capture
from tools.build_retained_producer_guard import symbols
from tools.two_player_combat import installed_policy,validate_ports


def audit(candidate,campaigns,instructions,renderer,route,renderer_audit,out):
    if out.exists():raise ValueError('Fresh output required')
    sources={}
    def bind(path):
        r=bound_report(path);sources.update(r['sources']);sources[str(path)]=sha(path);return r
    with installed_policy():
        receipt,strict,rows,_=combat.verify_pair(campaigns,'running-jumps','snes',candidate)
    ports=[]
    for kind in ('normal','observed'):
        root=campaigns/f'running-jumps-snes-{kind}'
        bind(root/'combat-observer.json');p=bind(root/'two-player.json')
        log=json.loads((root/'two-port-input.json').read_text())
        if validate_ports(log,rows,'snes')!=p['delivery']:raise ValueError('Changed port delivery')
        ports.append(log)
    if ports[0]!=ports[1]:raise ValueError('Observer changed controller inputs')
    busy=measure(strict,rows)
    ip=bind(instructions/'instruction-control.json');pp=bind(instructions/'two-player-instructions.json')
    if not ip['observer_neutral'] or not pp['observer_neutral']:raise ValueError('Nonneutral instructions')
    with installed_policy(),combat.installed('running-jumps'):
        ir,ir_rows=verify_capture(instructions)
    if ir_rows!=rows or ir['audio_sha256']!=receipt['audio_sha256']:
        raise ValueError('Instruction and sparse cores disagree')
    trace=instructions.with_suffix('.csv')
    if ip['sources'].get(str(trace))!=sha(trace):raise ValueError('Unbound instruction trace')
    with trace.open() as stream:full=[decode(r) for r in csv.reader(stream)]
    image=(candidate/'native-cpu.sfc').read_bytes()
    if any(image[r['pc']&0x3fffff]!=r['opcode'] for r in full):raise ValueError('Opcode mismatch')
    if any(b['clock']<=a['clock'] for a,b in zip(full,full[1:])):raise ValueError('Clock mismatch')
    runtime=symbols(candidate/'native_runtime.lbl');boot=symbols(candidate/'native_boot.lbl')
    queue=symbols(candidate/'queued-vblank.lbl')
    off=[r for r in busy['off_cadence'] if full[0]['frame']<=r['first']<r['last']<=full[-1]['frame']]
    intervals=[]
    for interval in off:
        r=interval_evidence(full,interval,runtime,boot,queue)
        r['hardware_before_finish']=[n for n in r['hardware_entries'] if n['clock']<r['finish']['clock']]
        r['hardware_after_finish']=[n for n in r['hardware_entries'] if n['clock']>=r['finish']['clock']]
        r['original_ticks_to_finish']=interval['nmi_advances']
        r['scope']+=' Before-finish and after-finish hardware entries are separated because the '
        r['scope']+='game tick count ends at completion, but physical start spacing ends at the next iteration.'
        intervals.append(r)
    if not intervals:raise ValueError('No covered remaining combat failure')
    display=observe(renderer,route,'snes');sources.update(display['sources'])
    if display['rom_sha256']!=sha(candidate/'native-cpu.sfc'):raise ValueError('Different rendered cartridge')
    rendered=bind(renderer_audit/'report.json')
    holds={k:summarize(v) for k,v in display['phases'].items()}
    paths=[Path(__file__),Path('tools/audit_queued_read_poll.py'),Path('tools/audit_busy_combat.py'),
        Path('tools/audit_display_cadence.py'),Path('tools/audit_uniform_holds.py'),
        candidate/'native_boot.lbl',candidate/'native_runtime.lbl',candidate/'queued-vblank.lbl']
    sources.update({str(p):sha(p) for p in paths})
    report=dict(strict_combat=strict,including_busy=busy,remaining_intervals=intervals,
        renderer=rendered,display=display,holds=holds,sources=sources,release_ready=False,
        physical_verified=False,pop_free_verified=False,scope=__doc__)
    out.mkdir(parents=True);(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(strict_passed=strict['passed'],histogram=busy['frame_histogram'],
        intervals=[dict(start=r['start'],finish=r['finish'],next_start=r['next_start'],
            before_finish=len(r['hardware_before_finish']),after_finish=len(r['hardware_after_finish'])) for r in intervals],
        renderer_passed=rendered['passed'],holds={k:dict(histogram=v['histogram'],
            short_irregular=len(v['short_irregular'])) for k,v in holds.items()})))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for k in ('candidate','campaigns','instructions','renderer','route','renderer-audit','out'):
        parser.add_argument('--'+k,type=Path,required=True)
    audit(**vars(parser.parse_args()))
