"""Audit a bracketed physical camera export without filling its sampling gaps."""
import argparse
from collections import Counter
import json
from pathlib import Path

from tools.audit_main_display_latency import bound_report
from tools.benchmark_report import sha
from tools.camera_state_log import decode


def bracket(before, after, repeated):
    """An exact paused resave must retain both the old prefix and new records."""
    initial, final = decode(before), decode(after)
    if after != repeated:
        raise ValueError('Paused resave changed; episode end is not stable')
    if final['total'] <= initial['total']:
        raise ValueError('No new camera samples')
    old = {r['sequence']: r for r in initial['records']}
    retained = {r['sequence']: r for r in final['records']}
    if any(retained.get(sequence) != row for sequence, row in old.items()):
        raise ValueError('Prior records changed or were overwritten')
    rows = [r for r in final['records'] if r['sequence'] >= initial['total']]
    if [r['sequence'] for r in rows] != list(range(initial['total'], final['total'])):
        raise ValueError('Incomplete new-record interval')
    return rows


def measure(rows):
    if len(rows) < 2:
        raise ValueError('Need at least two camera samples')
    if [r['sequence'] for r in rows] != list(range(rows[0]['sequence'], rows[-1]['sequence']+1)):
        raise ValueError('Missing or reordered sample sequence')
    pairs = []
    elapsed = 0
    for a, b in zip(rows, rows[1:]):
        ticks = (b['nmi']-a['nmi']) & 65535
        if not 0 < ticks < 32768:
            raise ValueError('Duplicate/backward/ambiguous NMI interval')
        elapsed += ticks
        served = ((b['served_lo']+256*b['served_hi'])-
                  (a['served_lo']+256*a['served_hi'])) & 65535
        pairs.append(dict(first_sequence=a['sequence'], next_sequence=b['sequence'],
            nmi_ticks=ticks, elapsed_nmi=elapsed, served_delta=served,
            same_room=a['room'] == b['room'],
            display_matches_previous_commit=b['display_camera'] == a['committed_camera'],
            working_delta=b['working_camera']-a['working_camera'],
            committed_delta=b['committed_camera']-a['committed_camera'],
            display_delta=b['display_camera']-a['display_camera']))
    adjacent = [p for p in pairs if p['nmi_ticks'] == 2 and p['same_room']]
    gaps = [p for p in pairs if p['nmi_ticks'] != 2 or not p['same_room']]
    return dict(samples=len(rows), first_sequence=rows[0]['sequence'], last_sequence=rows[-1]['sequence'],
        elapsed_nmi=elapsed, pairs=pairs, unobserved_intervals=gaps,
        sample_interval_histogram=dict(Counter(p['nmi_ticks'] for p in pairs)),
        adjacent_two_tick_samples=len(adjacent),
        adjacent_display_mismatches=[p for p in adjacent if not p['display_matches_previous_commit']],
        served_counter_total=sum(p['served_delta'] for p in pairs),
        served_counter_ratio_exceptions=[p for p in pairs if 2*p['served_delta'] != p['nmi_ticks']],
        working_commit_mismatches=[r['sequence'] for r in rows if r['working_camera'] != r['committed_camera']],
        interrupted_samples=[r['sequence'] for r in rows if r['nmi_changed_during_record']],
        fallback_values=sorted({r['fallback_lo']+256*r['fallback_hi'] for r in rows}),
        camera_ranges={k:[min(r[k] for r in rows),max(r[k] for r in rows)]
                       for k in ('working_camera','committed_camera','display_camera')})


def audit(before, after, repeated, out):
    if out.exists():
        raise ValueError('Fresh audit output required')
    sources = {str(Path(__file__)):sha(Path(__file__)),
        'tools/camera_state_log.py':sha(Path('tools/camera_state_log.py')),
        'tools/audio_packet_log.py':sha(Path('tools/audio_packet_log.py'))}
    snapshots = []
    identities = []
    for directory in (before, after, repeated):
        path = directory/'report.json'
        report = bound_report(path)
        snapshot = directory/report['accepted_file']
        if not report['passed'] or sha(snapshot) != report['sha256']:
            raise ValueError('Unqualified export')
        identities.append(report['remote'])
        sources.update(report['sources'])
        sources.update({str(p):sha(p) for p in (path,snapshot)})
        snapshots.append(snapshot.read_bytes())
    if len(set(identities)) != 1:
        raise ValueError('Exports come from different cartridges')
    rows = bracket(*snapshots)
    report = measure(rows)
    report.update(records=rows, sources=sources, paused_resave_exact=True,
        physical_speed_verified=False, physical_hold_explained=False, release_ready=False,
        scope='Only new records between explicit paused saves; exact repeated paused export. '
        'Two-tick neighbor comparisons test the previous-commit/display-shadow relation, not PPU '
        'readback. All wider intervals remain unobserved internally, even if the aggregate served '
        'counter advances once per two NMI ticks. Counter totals cannot prove intra-gap cadence. '
        'No video/NMI alignment, gap interpolation, audio qualification or original-speed claim.')
    out.mkdir(parents=True)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in
        ('pairs','records','sources','unobserved_intervals')}))


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('before','after','repeated','out'):
        parser.add_argument('--'+name,type=Path,required=True)
    audit(**vars(parser.parse_args()))
