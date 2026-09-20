"""Expose hybrid-noise source selection after nonzero volume publication."""
import argparse
import json
from pathlib import Path

from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha
from tools.review_native_transient_stems import same_core_load


def late_source(writes, packets):
    regs = [0]*128
    attacks = {p:dict(packet=p, exposure=[], source_writes=[]) for p in packets}
    for w in writes:
        p = w['packet']
        if p in attacks:
            attack = attacks[p]
            if w['register'] in (0x30,0x31) and w['value'] and not regs[0x3d] & 8:
                attack['exposure'].append(dict(**w, previous_non=regs[0x3d]))
            if w['register'] == 0x3d:
                attack['source_writes'].append(w)
        regs[w['register']] = w['value']
    for a in attacks.values():
        if not a['source_writes'] or a['source_writes'][-1]['value'] != 8:
            raise ValueError('Attack never selects expected built-in noise')
        switch = a['source_writes'][-1]
        a['late'] = bool(a['exposure'])
        a['volume_to_source_ticks'] = [switch['tick']-w['tick'] for w in a['exposure']]
        if any(n <= 0 for n in a['volume_to_source_ticks']):
            raise ValueError('Source chronology inconsistent')
    return list(attacks.values())


def audit(fixture, normal, observed, comparison, out):
    if out.exists():
        raise ValueError('Fresh audit required')
    prior = bound_report(comparison/'report.json')
    proof, _, writes, _ = same_core_load(observed, normal, fixture)
    if prior['sources'].get(str(normal/'audio.wav')) != sha(normal/'audio.wav'):
        raise ValueError('Attack comparison uses different PCM')
    packets = [r['first_frame'] for r in prior['fallback_attack_differences']]
    if not packets:
        raise ValueError('No failing fallback attacks to explain')
    attacks = late_source(writes, packets)
    if not all(a['late'] for a in attacks):
        raise ValueError('Observed failure does not match source-order hypothesis')
    # Trace-only sensitivity control: source select is moved before its volume
    # writes. This is not an executed repaired engine or fixed waveform claim.
    fixed = [dict(w) for w in writes]
    for p in packets:
        indices = [i for i,w in enumerate(fixed) if w['packet']==p]
        source = next(i for i in indices if fixed[i]['register']==0x3d)
        volume = next(i for i in indices if fixed[i]['register']==0x30)
        entry = fixed.pop(source)
        entry['tick'] = fixed[volume]['tick']-1
        fixed.insert(volume, entry)
    if any(a['late'] for a in late_source(fixed, packets)):
        raise ValueError('Reordered-source sensitivity control still fails')
    binding = bound_report(observed/'onset-observer.json')
    sources = {**prior['sources'], **proof['sources'], **binding['sources']}
    for p in (Path(__file__),Path('tests/test_noise_source_order.py'),
              Path('tools/audit_pulse_onset.py'), Path('tools/audit_dsp_latency.py'),
              comparison/'report.json', observed/'onset-observer.json'):
        sources[str(p)] = sha(p)
    report = dict(attacks=attacks, source_order_passed=False,
        trace_only_early_source_control_passed=True, repaired_engine_executed=False,
        observer_neutral=proof['observer_neutral'], sources=sources,
        physical_pop_causality_proven=False, release_ready=False,
        scope=__doc__+' Actual writes show NON still selects BRR when the two '
        'volumes become nonzero. This diagnoses the offline hybrid prototype, '
        'not the current game engine, which keeps built-in noise selected.')
    out.mkdir(parents=True)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('attacks','source_order_passed','trace_only_early_source_control_passed')}))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('fixture','normal','observed','comparison','out'):
        p.add_argument('--'+name,type=Path,required=True)
    audit(**vars(p.parse_args()))
