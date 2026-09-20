"""Validate exact-clock park stage observations and report missed NMI intervals.

Stage durations include everything between adjacent observed entry points; they
are not instruction-exclusive profiles. Fresh-process NTSC captures only.
"""
import argparse
from collections import defaultdict
import csv
import html
import json
from pathlib import Path

try:
    from .benchmark_report import verify_capture, sha
    from .capture_park_spans import POINTS
except ImportError:
    from benchmark_report import verify_capture, sha
    from capture_park_spans import POINTS

FRAME_CLOCKS = 357366
EDGES = ((8, 7), (7, 10), (10, 11), (11, 5), (5, 6), (6, 1),
         (1, 2), (2, 3), (3, 4), (4, 9))
LABELS = {i: point[0] for i, point in enumerate(POINTS)}


def parse(rows, binding):
    points = binding['points']
    if set(points) != {str(i) for i in LABELS}:
        raise ValueError('Missing/unknown timing point definitions')
    result = []
    for row in rows:
        if len(row) != 16:
            raise ValueError('Need sixteen-column absolute-clock span trace')
        values = [int(v, 16 if i == 5 else 10) for i, v in enumerate(row)]
        keys = ('event', 'frame', 'line', 'cycle', 'clock', 'pc', 'nmi',
                'task', 'transition', 'guard', 'room', 'pause', 'depth',
                'pending', 'oam_dirty', 'ppuctrl')
        r = dict(zip(keys, values))
        wanted = points.get(str(r['event']))
        if wanted is None or ((r['pc'] if len(wanted) > 4 else r['pc'] & 0xffff)
                              != int(wanted, 16)):
            raise ValueError('Trace PC does not match its bound timing point')
        if not binding['first'] <= r['frame'] <= binding['last']:
            raise ValueError('Trace frame outside bound observation window')
        if not 0 <= r['line'] < 262 or not 0 <= r['cycle'] < 1600:
            raise ValueError('Invalid NTSC beam position')
        if r['clock'] < 0 or (result and (r['clock'] <= result[-1]['clock']
                                        or r['frame'] < result[-1]['frame'])):
            raise ValueError('Nonmonotonic trace; reset/savestate unsupported')
        result.append(r)
    if not result or {r['event'] for r in result} != set(LABELS):
        raise ValueError('Empty/incomplete timing point coverage')
    return result


def stable(row):
    return (row['room'] == 3 and row['task'] & 0xc0 == 0xc0
            and not row['pause'] & 0x20 and not row['guard'] & 0x80
            and row['transition'] == 0)


def position(row):
    return {k: row[k] for k in ('frame', 'line', 'cycle', 'clock', 'nmi')}


def analyze(rows):
    durations = defaultdict(list)
    for a, b in zip(rows, rows[1:]):
        edge = (a['event'], b['event'])
        if edge in EDGES and stable(a) and stable(b) and a['nmi'] == b['nmi']:
            durations[edge].append(dict(clocks=b['clock']-a['clock'],
                                        start=position(a), end=position(b)))
    costs = {}
    for edge in EDGES:
        samples = durations[edge]
        if not samples:
            raise ValueError(f'No stable observations for edge {edge}')
        clocks = [s['clocks'] for s in samples]
        costs[' → '.join(LABELS[e] for e in edge)] = dict(
            samples=len(samples), minimum=min(clocks),
            mean=round(sum(clocks)/len(clocks), 2), maximum=max(clocks),
            worst=max(samples, key=lambda s: s['clocks']))
    entries = [i for i, r in enumerate(rows) if r['event'] == 0]
    gaps = []
    for left, right in zip(entries, entries[1:]):
        sample = rows[left:right+1]
        if not all(stable(r) for r in sample):
            continue
        elapsed = sample[-1]['clock']-sample[0]['clock']
        if elapsed <= 1.5*FRAME_CLOCKS:
            continue
        # Keep one entry into the polling loop, not every wait iteration.
        stages = [r for i, r in enumerate(sample)
                  if r['event'] != 9 or i == 0 or sample[i-1]['event'] != 9]
        polls = [r for r in sample if r['event'] == 9]
        gaps.append(dict(clocks=elapsed, nominal_frames=round(elapsed/FRAME_CLOCKS, 4),
            start=position(sample[0]), end=position(sample[-1]),
            stages=[dict(label=LABELS[r['event']], **position(r)) for r in stages],
            observed_poll_clocks=polls[-1]['clock']-polls[0]['clock'] if polls else 0))
    return dict(stage_costs=costs, late_nmi_intervals=gaps,
                late_nmi_interval_count=len(gaps), observed_rows=len(rows))


def build(capture, spans, out, normal=None):
    receipt, _ = verify_capture(capture)
    if (receipt['system'] != 'snes' or not receipt['capture_complete']
            or receipt['scenario_name'] not in ('traversal-park-stress','traversal-park-single-sweep')):
        raise ValueError('Need a complete SNES park capture')
    binding = receipt.get('span_trace', {})
    if binding.get('sha256') != sha(spans):
        raise ValueError('Span trace is not bound to this capture')
    with spans.open() as source:
        rows = parse(csv.reader(source), binding)
    report = analyze(rows)
    report['sources'] = dict(capture_sha256=sha(capture/'capture.json'),
        trace_sha256=sha(spans), rom_sha256=receipt['rom_sha256'],
        core_sha256=receipt['core_sha256'], audit_sha256=sha(Path(__file__)))
    report['observer_equivalence'] = None
    if normal is not None:
        reference, _ = verify_capture(normal)
        keys = ('rom_sha256', 'scenario_sha256', 'timeline_sha256', 'audio_sha256', 'frames')
        if not reference['capture_complete'] or any(reference[k] != receipt[k] for k in keys):
            raise ValueError('Observed run differs from its normal-core control')
        report['observer_equivalence'] = dict(passed=True, frames=receipt['frames'],
            normal_capture_sha256=sha(normal/'capture.json'), compared=list(keys))
    report['scope'] = ('Adjacent entry-point elapsed master clocks, not exclusive CPU costs. '
        'Stable unpaused room 3 only; observation window is not the entire park route. '
        'Late NMI-entry intervals measure interrupt cadence, not perceived audio fidelity '
        'or an NES/SNES combat-speed ratio. No production fix is certified here.')
    out.mkdir(parents=True, exist_ok=False)
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    cost_rows = ''.join('<tr>'+''.join(f'<td>{html.escape(str(v))}</td>' for v in
        (name, s['samples'], s['minimum'], s['mean'], s['maximum']))+'</tr>'
        for name, s in report['stage_costs'].items())
    (out/'index.html').write_text('''<!doctype html><meta charset="utf-8">
<title>Park frame-cost evidence</title><style>body{background:#111820;color:#eee;
font:16px system-ui;max-width:1100px;margin:30px auto}td,th{padding:8px;text-align:left}
a{color:#9cf}pre{white-space:pre-wrap}table{border-collapse:collapse}tr{border-bottom:1px solid #345}</style>
<h1>Park interrupt and graphics costs</h1><p>'''+html.escape(report['scope'])+
        '</p><p><a href="report.json">Full measurements and source hashes</a></p>'+
        f'<p>Late interrupt intervals in this window: {len(report["late_nmi_intervals"])}</p>'+
        '<table><tr><th>Entry → entry</th><th>Samples</th><th>Minimum</th><th>Mean</th><th>Maximum clocks</th></tr>'+
        cost_rows+'</table><h2>Late interval stage positions</h2><pre>'+
        html.escape(json.dumps(report['late_nmi_intervals'], indent=2))+'</pre>')
    print(json.dumps({k: report[k] for k in ('late_nmi_interval_count', 'observer_equivalence')}, indent=2))
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('capture', 'spans', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    p.add_argument('--normal', type=Path)
    a = p.parse_args()
    build(a.capture, a.spans, a.out, a.normal)
