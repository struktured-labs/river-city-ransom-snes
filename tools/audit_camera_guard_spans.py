"""Account for actual admitted/deferred producer calls and frame interrupt coverage."""
import argparse
from collections import Counter
import csv
import json
from pathlib import Path

from tools.audit_main_display_latency import bound_report
from tools.audit_route_loop_cadence import stable_room
from tools.benchmark_report import sha, verify_capture
from tools.capture_combat_instructions import equivalent
from tools.capture_camera_guard_spans import points
from tools.combat_campaign import installed


def account(events):
    guard = None
    fallback = None
    service = None
    pending = None
    calls, guards, fallbacks, producers, nmis = [], [], [], [], []
    for e in events:
        name = e['name']
        if name == 'guard':
            if guard or fallback or service:
                raise ValueError('Nested camera guard')
            guard = dict(entry=e, pending_beam=None, admit=None)
        elif name == 'pending_beam':
            if guard is None or guard['pending_beam'] is not None:
                raise ValueError('Unpaired pending-beam read')
            guard['pending_beam'] = e
        elif name == 'admit':
            if guard is None or guard['pending_beam'] is None or guard['admit'] is not None:
                raise ValueError('Unpaired admission')
            guard['admit'] = e
        elif name == 'guard_return':
            if guard is None or guard['admit'] is not None:
                raise ValueError('Unexpected guard return')
            guard.update(after=e, outcome='deferred' if guard['pending_beam'] else 'empty')
            if guard['pending_beam']:
                if pending is not None:
                    raise ValueError('Repeated deferral before service needs explicit accounting')
                pending = len(guards)
            guards.append(guard)
            guard = None
        elif name == 'fallback':
            if fallback is not None or guard or service:
                raise ValueError('Nested fallback')
            fallback = dict(entry=e, serviced=False)
        elif name == 'fallback_return':
            if fallback is None or service:
                raise ValueError('Unpaired fallback return')
            fallback['after'] = e
            fallbacks.append(fallback)
            fallback = None
        elif name == 'service':
            if service is not None or not (fallback or (guard and guard['admit'])):
                raise ValueError('Unowned or nested service')
            service = dict(entry=e, origin='fallback' if fallback else 'camera', phases=[])
            if fallback:
                if fallback['serviced']:
                    raise ValueError('Duplicate fallback service')
                fallback['serviced'] = True
            if pending is not None:
                guards[pending]['served_at'] = e
                service['deferred_guard'] = pending
                pending = None
        elif name == 'service_return':
            if service is None:
                raise ValueError('Unpaired service return')
            if [p['name'] for p in service['phases']] != ['producer', 'palette', 'sprites', 'tail']:
                raise ValueError('Missing/duplicate/reordered real production phases')
            service.update(after=e, elapsed_clocks=e['clock']-service['entry']['clock'])
            if service['origin'] == 'camera':
                service['before_vblank'] = (e['frame'] == guard['admit']['frame'] and e['line'] < 240)
                guard.update(after=e, outcome='admitted')
                guards.append(guard)
                guard = None
            calls.append(service)
            service = None
        elif name in ('producer', 'palette', 'sprites', 'tail'):
            if name == 'producer':
                producers.append(dict(**e, owner=service['origin'] if service else 'ordinary'))
            if service is not None:
                service['phases'].append(e)
        elif name == 'nmi':
            if guard or service or fallback:
                raise ValueError('Interrupt entered masked scheduling path')
            nmis.append(e)
    if guard or service or fallback or pending is not None:
        raise ValueError('Truncated scheduling/service ownership')
    if not guards or not calls or not nmis:
        raise ValueError('Missing scheduling coverage')
    return dict(guards=guards, services=calls, fallbacks=fallbacks,
                producers=producers, nmis=nmis)


def audit(candidate, capture, normal, out):
    if out.exists():
        raise ValueError('Fresh output required')
    binding = bound_report(capture/'guard-spans.json')
    bound_report(normal/'instruction-control.json')
    if points(candidate) != binding['points']:
        raise ValueError('Different linked observation sites')
    with installed('sustained-attacks'):
        receipt, rows = verify_capture(capture)
        control, plain = verify_capture(normal)
    equivalent(receipt, rows, control, plain)
    if sha(candidate/'native-cpu.sfc') != receipt['rom_sha256']:
        raise ValueError('Different observed cartridge')
    trace = Path(binding['trace'])
    names = {p['index']: p for p in binding['points']}
    events = []
    with trace.open() as stream:
        for raw in csv.reader(stream):
            if len(raw) != 16:
                raise ValueError('Unexpected span schema')
            values = [int(v, 16 if i == 5 else 10) for i, v in enumerate(raw)]
            event, frame, line, cycle, clock, pc, nmi = values[:7]
            if event not in names or not 1 <= frame <= receipt['frames']:
                raise ValueError('Unknown point or frame')
            site = names[event]
            wanted = int(site['pc'], 16)
            if ((len(site['pc']) > 4 and pc != wanted) or
                    (len(site['pc']) == 4 and (pc & 65535 != wanted or not 0xC1 <= pc >> 16 <= 0xC8))):
                raise ValueError('Wrong program bank or point')
            if events and clock <= events[-1]['clock']:
                raise ValueError('Nonmonotonic clock')
            events.append(dict(name=site['name'], frame=frame, line=line, cycle=cycle,
                               clock=clock, pc=pc, nmi=nmi))
    result = account(events)
    eligible = [r['frame'] for i, r in enumerate(rows[1:-1], 1)
                if stable_room(rows[i-1:i+1]) is not None
                and all(p['native']['ppu_ctrl'] & 128 for p in rows[i-1:i+1])]
    counts = Counter(e['frame'] for e in result['nmis'])
    failures = [dict(frame=f, entries=counts[f]) for f in eligible if counts[f] != 1]
    admitted = [s for s in result['services'] if s['origin'] == 'camera']
    fallback_ticks = {s['entry']['nmi'] for s in result['services'] if s['origin'] == 'fallback'}
    duplicated = {str(t): [p for p in result['producers'] if p['nmi'] == t]
                  for t in sorted(fallback_ticks)}
    gates = dict(admitted_services_before_vblank=bool(admitted) and all(s['before_vblank'] for s in admitted),
                 stable_frames_have_one_nmi=bool(eligible) and not failures,
                 deferred_jobs_serviced=all('served_at' in g for g in result['guards'] if g['outcome'] == 'deferred'))
    result.update(passed=all(gates.values()), gates=gates, stable_frames=len(eligible),
        nmi_coverage_failures=failures, producer_calls_on_fallback_ticks=duplicated,
        admitted_max_elapsed_clocks=max(s['elapsed_clocks'] for s in admitted),
        outcomes=dict(Counter(g['outcome'] for g in result['guards'])),
        sources={**binding['sources'], **{str(p): sha(p) for p in (Path(__file__),
            Path('tools/audit_main_display_latency.py'), Path('tools/audit_route_loop_cadence.py'),
            Path('tools/benchmark_report.py'), Path('tools/capture_combat_instructions.py'),
            Path('tools/capture_camera_guard_spans.py'), Path('tools/combat_campaign.py'),
            candidate/'native-cpu.sfc', capture/'guard-spans.json', normal/'instruction-control.json',
            capture/'capture.json', normal/'capture.json', capture/'timeline.json', normal/'timeline.json', trace)}},
        observer_neutral=True, production_worst_case_bound_proven=False, release_ready=False,
        scope='All observed guard/service/fallback paths in a complete same-core-neutral sustained-attack '
        'episode. Four actual production phases required per service; deferred ownership must terminate '
        'exactly once. Real NMI entry coverage checked on every stable NMI-enabled sampled frame. '
        'All producer calls on fallback ticks retained, including ordinary additional work. Measured '
        'maxima are empirical, NOT a worst-case bound or full-game/audio certification.')
    out.mkdir(parents=True)
    (out/'report.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k: result[k] for k in ('passed','gates','stable_frames','outcomes','admitted_max_elapsed_clocks')}))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('candidate','capture','normal','out'):
        p.add_argument('--'+name, type=Path, required=True)
    audit(**vars(p.parse_args()))
