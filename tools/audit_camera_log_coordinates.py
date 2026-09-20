"""Keyed renderer comparison: keep extra/missing events without positional cascades."""
import argparse
import csv
import html
from itertools import groupby
import json
from pathlib import Path

from tools.audit_main_display_latency import bound_report
from tools.audit_scroll_splits import eligible
from tools.benchmark_report import sha, verify_capture


def frames(source):
    previous = 0
    for frame, rows in groupby(source, lambda r: int(r['frame'])):
        if frame <= previous:
            raise ValueError('Reordered frame groups')
        previous = frame
        lines = {}
        last_line = -1
        for row in rows:
            line = int(row['line'])
            if not 32 <= line < 192 or line < last_line:
                raise ValueError('Invalid/reordered scanline')
            last_line = line
            lines.setdefault(line, []).append(row)
        yield frame, lines


def compare(left, right, eligible_frames):
    iterators = [iter(frames(left)), iter(frames(right))]
    heads = [next(i, None) for i in iterators]
    differences = []
    counts = [0, 0]
    covered = [set(), set()]
    while any(h is not None for h in heads):
        frame = min(h[0] for h in heads if h is not None)
        pair = []
        for side in range(2):
            h = heads[side]
            lines = h[1] if h is not None and h[0] == frame else {}
            pair.append(lines)
            counts[side] += sum(len(rows) for rows in lines.values())
            if frame in eligible_frames and set(lines) == set(range(32, 192)) and all(
                    len(rows) == 1 for rows in lines.values()):
                covered[side].add(frame)
            if h is not None and h[0] == frame:
                heads[side] = next(iterators[side], None)
        for line in sorted(pair[0].keys() | pair[1].keys()):
            a, b = pair[0].get(line, []), pair[1].get(line, [])
            if a != b:
                differences.append(dict(frame=frame, line=line, baseline=a, diagnostic=b,
                    eligible_game_frame=frame in eligible_frames,
                    bg1_enabled_in_either=any(int(r['main_screen']) & 1 and not int(r['forced_blank'])
                                             for r in a+b)))
    missing = [sorted(eligible_frames-c) for c in covered]
    return dict(baseline_rows=counts[0], diagnostic_rows=counts[1],
        exact=bool(counts[0]) and not differences, differences=differences,
        eligible_frames=len(eligible_frames), missing_eligible_coverage=missing,
        eligible_camera_match=bool(eligible_frames) and not any(missing) and not any(
            d['eligible_game_frame'] for d in differences))


def audit(parent, diagnostic, normal, review, out):
    if out.exists():
        raise ValueError('Fresh output required')
    receipt, rows = verify_capture(normal)
    evidence = bound_report(review/'report.json')
    if (evidence['sources'].get(str(normal/'capture.json')) != sha(normal/'capture.json')
            or not evidence['results']['wait-route']['camera_fields_exact']
            or not receipt['capture_complete']):
        raise ValueError('Need authenticated complete matching-camera route')
    sources = dict(evidence['sources'])
    traces = []
    for folder in (parent, diagnostic):
        p = folder/'renderer-observer.json'
        proof = bound_report(p)
        if not proof['observer_neutral'] or proof['frames'] != receipt['frames']:
            raise ValueError('Unqualified renderer observer')
        sources.update(proof['sources'])
        sources[str(p)] = sha(p)
        traces.append(Path(proof['trace']))
    selected = {r['frame'] for p, r in zip(rows, rows[1:]) if eligible(p) and eligible(r)}
    with traces[0].open() as a, traces[1].open() as b:
        result = compare(csv.DictReader(a), csv.DictReader(b), selected)
    for p in (Path(__file__), Path('tests/test_camera_log_coordinates.py'),
              Path('tools/audit_scroll_splits.py'), review/'report.json'):
        sources[str(p)] = sha(p)
    report = dict(result=result, sources=sources, full_observer_neutral=False,
                  physical_deployed=False, release_ready=False,
                  scope='Actual frame/scanline keys, not temporal alignment or resampling. '
                  'Every missing/extra/duplicate event retained. Existing consecutive active-game '
                  'eligibility requires all160 scanlines in both streams. No complete-event match '
                  'claimed when an extra disabled-BG event exists. Logger still changes sprites '
                  'and PCM; no physical camera, original-speed, or pop-free certification.')
    out.mkdir(parents=True)
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Camera recorder scanline keys</title>'
        '<style>body{background:#101820;color:#eef;font:18px system-ui;max-width:1050px;margin:40px auto}'
        'a{color:#8df}pre{white-space:pre-wrap}</style><h1>Camera recorder: keyed scanline comparison</h1><p>'
        +html.escape(report['scope'])+'</p><p>'
        +f'{result["eligible_frames"]:,} active-game frames, all160 lines required in each. '
        +f'Active camera match: {result["eligible_camera_match"]}. '
        +f'Entire renderer event stream match: {result["exact"]}.</p><h2>All differing coordinates</h2><pre>'
        +html.escape(json.dumps(result['differences'],indent=2))+'</pre><p>'
        '<a href="../camera-wait-review-2444/">Retained sprite/audio failures and collages</a> · '
        '<a href="report.json">Source-bound report</a></p>')
    report['artifacts'] = {'index.html': sha(out/'index.html')}
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k != 'differences'}))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('parent', 'diagnostic', 'normal', 'review', 'out'):
        p.add_argument('--'+name,type=Path,required=True)
    audit(**vars(p.parse_args()))
