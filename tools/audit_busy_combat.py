"""Keep in-progress original NMI work in the combat-speed denominator.

$0107 bit7 is set by the original NMI body and cleared before its return.
Excluding every frame where it is set can hide exactly the interrupt overruns
under investigation. Keep the old strict results and old stable summary, and
add a room-stable summary which explicitly includes this flag.
"""
import argparse
from collections import Counter
import csv
import json
from pathlib import Path

from tools import combat_campaign as combat
from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha
from tools.build_retained_producer_guard import symbols
from tools.review_two_player_combat import stable_gaps
from tools.two_player_combat import installed_policy, validate_ports


def classify(rows):
    rooms = set()
    busy = []
    reasons = []
    for row in rows:
        ram = bytes.fromhex(row['game_ram_hex'])
        if len(ram) != 2048:
            raise ValueError('Incomplete original RAM')
        rooms.add(ram[0x42])
        if ram[0x107]&128:
            busy.append(row['frame'])
        checks = dict(task=ram[0x100]!=0xc0,pause=bool(ram[0x3f]&32),
                      flags=bool(ram[0x3e]&130),fade=ram[0x692]!=4,
                      transition=bool(row['native']['transition_state']))
        if any(checks.values()):
            reasons.append(dict(frame=row['frame'],reasons=[k for k,v in checks.items() if v]))
    room = next(iter(rooms)) if len(rooms)==1 else None
    if room not in range(4):
        reasons.append(dict(reason='room changed or outside sampled rooms',rooms=sorted(rooms)))
    return dict(room=room if not reasons else None,busy_frames=busy,exclusions=reasons)


def measure(result,rows):
    loops = sorted(result['iterations']+result['other_iterations'],key=lambda r:r['start']['clock'])
    selected, excluded = [], []
    for a,b in zip(loops,loops[1:]):
        first,last = a['start']['frame'],b['start']['frame']
        context = classify(rows[first-1:last])
        record = dict(first=first,last=last,frames=last-first,context=context,
                      nmi_advances=a['nmi_advances'],start=a['start'],finish=a['finish'],
                      next_start=b['start'],commit=a.get('commit'))
        (selected if context['room'] is not None else excluded).append(record)
    off = [r for r in selected if r['frames']!=2 or r['nmi_advances']!=2]
    return dict(intervals=len(selected),frame_histogram=dict(Counter(r['frames'] for r in selected)),
                passed=bool(selected) and not off,off_cadence=off,
                excluded=excluded,busy_intervals=[r for r in selected if r['context']['busy_frames']],
                scope='Includes original NMI-busy frames; task/pause/fade/transition/room exclusions retained. '
                      'Not matched NES workload or a full-game speed certificate.')


def audit(candidate,campaigns,instructions,out):
    if out.exists():
        raise ValueError('Fresh output required')
    sources = {}
    details = {}
    with installed_policy():
        for policy in combat.POLICIES:
            receipt,result,rows,_ = combat.verify_pair(campaigns,policy,'snes',candidate)
            records = []
            for kind in ('normal','observed'):
                folder = campaigns/f'{policy}-snes-{kind}'
                port = bound_report(folder/'two-player.json')
                observer = bound_report(folder/'combat-observer.json')
                record = json.loads((folder/'two-port-input.json').read_text())
                if validate_ports(record,rows,'snes') != port['delivery']:
                    raise ValueError('Different actual input ports')
                records.append(record)
                sources.update(port['sources']);sources.update(observer['sources'])
                for p in (folder/'two-player.json',folder/'combat-observer.json'):
                    sources[str(p)] = sha(p)
            if records[0] != records[1]:
                raise ValueError('Observation changed ports')
            details[policy] = dict(strict=result,old_stable=stable_gaps(result,rows,'snes'),
                                   including_busy=measure(result,rows),frames=receipt['frames'])
    instruction_proof = bound_report(instructions/'instruction-control.json')
    ports = bound_report(instructions/'two-player-instructions.json')
    if not instruction_proof['observer_neutral'] or not ports['observer_neutral']:
        raise ValueError('Instruction window is not neutral')
    rom = candidate/'native-cpu.sfc'
    if instruction_proof['sources'].get(str(rom)) != sha(rom):
        raise ValueError('Different instruction cartridge')
    sources.update(instruction_proof['sources']);sources.update(ports['sources'])
    trace = instructions.with_suffix('.csv')
    if sources.get(str(trace)) != sha(trace):
        raise ValueError('Unbound instructions')
    image = rom.read_bytes()
    boot = symbols(candidate/'native_boot.lbl')
    edges = []
    for row in csv.reader(trace.open()):
        pc = int(row[4],16)
        if pc == boot['nmi']:
            kind = 'native_nmi'
        elif pc>>16 in range(0xc1,0xc9) and pc&65535 in (0xf189,0xf1b1):
            at = (pc>>16&63)*65536+(pc&65535)
            if image[at:at+3] != bytes.fromhex('8d0701'):
                raise ValueError('Wrong busy-flag instruction')
            kind = 'set_busy' if pc&65535==0xf189 else 'clear_busy'
            if int(row[6])&255 != (128 if kind=='set_busy' else 0):
                raise ValueError('Unexpected busy-flag value')
        else:
            continue
        edges.append(dict(kind=kind,frame=int(row[0]),line=int(row[1]),cycle=int(row[2]),
                          clock=int(row[3]),pc=pc,a=int(row[6])))
    if not all(any(r['kind']==kind for r in edges) for kind in ('native_nmi','set_busy','clear_busy')):
        raise ValueError('Missing executed flag/NMI evidence')
    paths = [Path(__file__),Path('tools/review_two_player_combat.py'),Path('tools/audit_route_loop_cadence.py'),
             Path('tools/combat_campaign.py'),Path('tools/two_player_combat.py'),
             Path('tools/build_retained_producer_guard.py'),Path('tests/test_busy_combat.py'),
             instructions/'instruction-control.json',instructions/'two-player-instructions.json',
             rom,candidate/'manifest.json',candidate/'native_boot.lbl']
    sources.update({str(p):sha(p) for p in paths})
    report = dict(campaigns=details,executed_busy_flag_edges=edges,sources=sources,release_ready=False,
                  strict_passed=all(r['strict']['passed'] for r in details.values()),
                  including_busy_passed=all(r['including_busy']['passed'] for r in details.values()),scope=__doc__)
    out.mkdir(parents=True)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({p:dict(old_stable=r['old_stable']['frame_histogram'],
        including_busy=r['including_busy']['frame_histogram'],strict_passed=r['strict']['passed'])
        for p,r in details.items()}))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('candidate','campaigns','instructions','out'):
        p.add_argument('--'+name,type=Path,required=True)
    audit(**vars(p.parse_args()))
